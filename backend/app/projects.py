from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.auth import require_user
from app.db import connect
from app.ingestion import parse_sheets
from app.ontology import summarize_ontology

router = APIRouter(prefix="/api", dependencies=[Depends(require_user)])


class ProjectCreate(BaseModel):
    name: str
    description: str = ""


class ProjectUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


@router.get("/projects")
def list_projects():
    conn = connect()
    rows = conn.execute(
        "SELECT p.*, "
        "(SELECT COUNT(*) FROM agents a WHERE a.show_project_id = p.id) AS agent_count "
        "FROM show_projects p ORDER BY p.created_at DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@router.post("/projects", status_code=201)
def create_project(payload: ProjectCreate):
    if not payload.name.strip():
        raise HTTPException(400, "Project name is required")
    conn = connect()
    cur = conn.execute(
        "INSERT INTO show_projects (name, description) VALUES (?, ?)",
        (payload.name.strip(), payload.description),
    )
    conn.commit()
    row = conn.execute(
        "SELECT * FROM show_projects WHERE id = ?", (cur.lastrowid,)
    ).fetchone()
    conn.close()
    return dict(row)


@router.get("/projects/{project_id}")
def get_project(project_id: int):
    conn = connect()
    row = conn.execute(
        "SELECT * FROM show_projects WHERE id = ?", (project_id,)
    ).fetchone()
    conn.close()
    if row is None:
        raise HTTPException(404, "Show project not found")
    return dict(row)


def _list_sheets(location: str | None, name: str) -> list[dict]:
    """Enumerate the tabs/record sets inside a data source file. A multi-tab
    Excel workbook returns one entry per tab; CSV/JSON return a single entry.
    Best-effort — a missing or unparseable file yields no tabs."""
    try:
        if not location or not Path(location).exists():
            return []
        sheets = parse_sheets(Path(location).read_bytes(), name)
        return [{"name": tab, "records": len(rows)} for tab, rows in sheets.items()]
    except Exception:
        return []


@router.get("/projects/{project_id}/describe")
def describe_project(project_id: int, request: Request):
    """Read every component of a project — data sources, the ontology layer
    summary, and agents — for the layered "Describe Project" view."""
    conn = connect()
    project = conn.execute(
        "SELECT * FROM show_projects WHERE id = ?", (project_id,)
    ).fetchone()
    if project is None:
        conn.close()
        raise HTTPException(404, "Show project not found")
    ds_rows = conn.execute(
        "SELECT id, name, type, status, created_at, location FROM data_sources "
        "WHERE show_project_id = ? ORDER BY created_at",
        (project_id,),
    ).fetchall()
    agents = [
        dict(r)
        for r in conn.execute(
            "SELECT id, name, type, model_provider, model_name, data_source_id "
            "FROM agents WHERE show_project_id = ? ORDER BY created_at",
            (project_id,),
        ).fetchall()
    ]
    conn.close()

    # Expand each data source into its tabs so multi-tab workbooks surface every
    # tab as its own component in the Describe view.
    data_sources = []
    for r in ds_rows:
        ds = {k: r[k] for k in ("id", "name", "type", "status", "created_at")}
        ds["sheets"] = _list_sheets(r["location"], r["name"])
        data_sources.append(ds)

    ontology = {"classes": [], "relations": [], "node_total": 0, "relation_total": 0}
    try:
        driver = request.app.state.neo4j
        driver.verify_connectivity()
        ontology = summarize_ontology(driver, project_id)
    except Exception:
        pass  # Neo4j unavailable → empty ontology summary

    return {
        "project": {
            "id": project["id"],
            "name": project["name"],
            "description": project["description"],
        },
        "data_sources": data_sources,
        "ontology": ontology,
        "agents": agents,
    }


@router.patch("/projects/{project_id}")
def update_project(project_id: int, payload: ProjectUpdate):
    fields = payload.model_dump(exclude_unset=True)
    conn = connect()
    if conn.execute(
        "SELECT 1 FROM show_projects WHERE id = ?", (project_id,)
    ).fetchone() is None:
        conn.close()
        raise HTTPException(404, "Show project not found")
    if fields:
        assignments = ", ".join(f"{key} = ?" for key in fields)
        conn.execute(
            f"UPDATE show_projects SET {assignments}, updated_at = datetime('now') "
            "WHERE id = ?",
            (*fields.values(), project_id),
        )
        conn.commit()
    row = conn.execute(
        "SELECT * FROM show_projects WHERE id = ?", (project_id,)
    ).fetchone()
    conn.close()
    return dict(row)


@router.delete("/projects/{project_id}", status_code=204)
def delete_project(project_id: int):
    conn = connect()
    cur = conn.execute("DELETE FROM show_projects WHERE id = ?", (project_id,))
    conn.commit()
    conn.close()
    if cur.rowcount == 0:
        raise HTTPException(404, "Show project not found")
