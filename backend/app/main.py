import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from neo4j import GraphDatabase

from app import agents, auth, chat, ingestion, ontology_agent, projects
from app.db import connect, init_db
from app.graph import init_graph

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://neo4j:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")


def backfill_neo4j_projects(driver) -> None:
    """Tag pre-Show-Project graph data with its project so it stays visible.
    Entities carry a source_id, so map each to its data source's project;
    class/relation nodes predate scoping, so assign any untagged ones to the
    single migration project. Idempotent (only touches rows missing project_id).
    """
    conn = connect()
    sources = conn.execute(
        "SELECT id, show_project_id FROM data_sources "
        "WHERE show_project_id IS NOT NULL"
    ).fetchall()
    default = conn.execute(
        "SELECT id FROM show_projects WHERE name = 'Default Show' ORDER BY id LIMIT 1"
    ).fetchone()
    conn.close()
    with driver.session() as session:
        for s in sources:
            session.run(
                "MATCH (e:Entity {source_id: $sid}) WHERE e.project_id IS NULL "
                "SET e.project_id = $pid",
                sid=s["id"], pid=s["show_project_id"],
            )
        if default is not None:
            session.run(
                "MATCH (c:OntologyClass) WHERE c.project_id IS NULL "
                "SET c.project_id = $pid",
                pid=default["id"],
            )
            session.run(
                "MATCH (r:OntologyRelation) WHERE r.project_id IS NULL "
                "SET r.project_id = $pid",
                pid=default["id"],
            )


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    app.state.neo4j = GraphDatabase.driver(
        NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD)
    )
    try:
        init_graph(app.state.neo4j)
        backfill_neo4j_projects(app.state.neo4j)
    except Exception as exc:
        # Neo4j may not be reachable yet in local dev; health reports its status.
        print(f"Neo4j schema init skipped: {exc}")
    yield
    app.state.neo4j.close()


app = FastAPI(title="ShowSphere", lifespan=lifespan)
app.include_router(auth.router)
app.include_router(projects.router)
app.include_router(agents.router)
app.include_router(ingestion.router)
app.include_router(chat.router)
app.include_router(ontology_agent.router)


@app.get("/api/health")
def health():
    try:
        app.state.neo4j.verify_connectivity()
        neo4j_status = "up"
    except Exception:
        neo4j_status = "down"
    return {"status": "ok", "neo4j": neo4j_status}
