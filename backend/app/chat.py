import json
import re

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app import booth_pipeline
from app.auth import require_user
from app.db import connect
from app.llm import get_provider
from app.ontology import retrieve_context, summarize_ontology

router = APIRouter(prefix="/api", dependencies=[Depends(require_user)])

ARTIFACT_TYPES = {"bar", "line", "table", "metrics", "map"}
GROUNDING_RULES = (
    "STRICT GROUNDING — read carefully. This project has a knowledge graph "
    "(ontology) built from the exhibitor's ingested data. You may answer ONLY "
    "using the ontology and data provided below; treat it as your single source "
    "of truth. Do NOT use outside or prior knowledge, and never invent entities, "
    "values, or relationships that are not present in the provided data. If the "
    "answer is not contained in the ontology and data below, say plainly that the "
    "project's data does not contain that information, and (when useful) point to "
    "what the ontology does cover. Do not speculate or generalise beyond the data."
)

CANVAS_RE = re.compile(r"```canvas\s*(\{.*?\})\s*```", re.DOTALL)
CANVAS_GUIDE = (
    "When a visualization would help, append exactly one fenced block "
    "```canvas {JSON} ``` to your reply. Use one of these shapes:\n"
    '{"type":"bar","title":"...","data":[{"label":"A","value":10}]}\n'
    '{"type":"line","title":"...","data":[{"label":"Jan","value":5}]}\n'
    '{"type":"metrics","title":"...","items":[{"label":"Booths","value":42}]}\n'
    '{"type":"table","title":"...","columns":["A","B"],"rows":[["x","y"]]}\n'
    '{"type":"map","title":"...","points":[{"lat":52.5,"lng":13.4,"label":"Berlin"}]}\n'
    "Only include the block when a chart, table, metrics, or map is genuinely useful."
)


def extract_artifact(text: str) -> tuple[str, dict | None]:
    match = CANVAS_RE.search(text)
    if not match:
        return text, None
    try:
        artifact = json.loads(match.group(1))
    except json.JSONDecodeError:
        return text, None
    if not isinstance(artifact, dict) or artifact.get("type") not in ARTIFACT_TYPES:
        return text, None
    clean = (text[: match.start()] + text[match.end() :]).strip()
    return clean, artifact


class ChatRequest(BaseModel):
    content: str


def _session_id(conn, agent_id: int, username: str) -> int:
    row = conn.execute(
        "SELECT id FROM chat_sessions WHERE agent_id = ? ORDER BY created_at LIMIT 1",
        (agent_id,),
    ).fetchone()
    if row:
        return row["id"]
    user = conn.execute(
        "SELECT id FROM users WHERE username = ?", (username,)
    ).fetchone()
    cur = conn.execute(
        "INSERT INTO chat_sessions (agent_id, user_id) VALUES (?, ?)",
        (agent_id, user["id"] if user else None),
    )
    return cur.lastrowid


def _ontology_context(request: Request, query: str, project_id: int) -> dict:
    """Gather everything the agent is allowed to reason over: a high-level
    overview of the project's ontology (so it knows the universe of entities even
    when a query matches no specific record) plus the records and relationships
    that match the question."""
    base = {"overview": None, "context": "", "traversal": {"nodes": [], "edges": []}}
    try:
        driver = request.app.state.neo4j
        driver.verify_connectivity()
        overview = summarize_ontology(driver, project_id)
        retrieved = retrieve_context(driver, query, project_id)
        return {"overview": overview, **retrieved}
    except Exception:
        return base


def _build_system(config: dict, grounding: dict) -> str:
    """Assemble a strictly-grounded system prompt: the agent may only use the
    project's ontology and ingested data, never outside knowledge."""
    system = "You are an InShow exhibitor-services agent for trade shows."
    if config.get("ontology_instructions"):
        system += "\n\n" + config["ontology_instructions"]
    system += "\n\n" + GROUNDING_RULES

    overview = grounding.get("overview")
    if overview and overview.get("node_total"):
        classes = ", ".join(
            f"{c['name']} (×{c['count']})" for c in overview["classes"]
        )
        rels = ", ".join(
            f"{r['name']} (×{r['count']})" for r in overview["relations"]
        )
        system += (
            f"\n\nProject ontology layer — {overview['node_total']} nodes, "
            f"{overview['relation_total']} relationships."
            f"\nNode types: {classes or 'none'}."
            f"\nRelationship types: {rels or 'none'}."
        )
    else:
        system += (
            "\n\nThis project has no ingested data or ontology yet, so you have no "
            "facts to answer from. Tell the user to ingest data and build the "
            "ontology first."
        )

    if grounding.get("context"):
        system += (
            "\n\nData relevant to the question (entities, their properties, and "
            "relationships — your only source of facts):\n" + grounding["context"]
        )
    elif overview and overview.get("node_total"):
        system += (
            "\n\nNo specific records matched this question. Answer only if the "
            "ontology overview above already contains the answer; otherwise say "
            "the project's data does not cover it."
        )

    system += "\n\n" + CANVAS_GUIDE
    return system


@router.get("/agents/{agent_id}/messages")
def history(agent_id: int):
    conn = connect()
    rows = conn.execute(
        "SELECT m.role, m.content, m.metadata, m.created_at FROM messages m "
        "JOIN chat_sessions s ON m.session_id = s.id "
        "WHERE s.agent_id = ? ORDER BY m.created_at",
        (agent_id,),
    ).fetchall()
    conn.close()
    return [
        {
            "role": r["role"],
            "content": r["content"],
            "metadata": json.loads(r["metadata"]),
            "created_at": r["created_at"],
        }
        for r in rows
    ]


@router.post("/agents/{agent_id}/chat")
def chat(
    agent_id: int,
    payload: ChatRequest,
    request: Request,
    username: str = Depends(require_user),
):
    conn = connect()
    agent = conn.execute(
        "SELECT * FROM agents WHERE id = ?", (agent_id,)
    ).fetchone()
    if agent is None:
        conn.close()
        raise HTTPException(404, "Agent not found")

    session_id = _session_id(conn, agent_id, username)
    conn.execute(
        "INSERT INTO messages (session_id, role, content) VALUES (?, 'user', ?)",
        (session_id, payload.content),
    )
    conn.commit()

    prior = conn.execute(
        "SELECT role, content FROM messages WHERE session_id = ? ORDER BY created_at",
        (session_id,),
    ).fetchall()
    config = json.loads(agent["config"])

    # Booth Layout agents run the deterministic spatial pipeline instead of the
    # generic ontology-grounded chat. The prior layout "program" is carried in
    # the last assistant message metadata so feedback iterates on it.
    if agent["type"] == "booth_layout":
        prev_row = conn.execute(
            "SELECT metadata FROM messages WHERE session_id = ? AND role = 'assistant' "
            "ORDER BY created_at DESC LIMIT 1",
            (session_id,),
        ).fetchone()
        conn.close()
        prev_program = None
        if prev_row:
            try:
                prev_program = json.loads(prev_row["metadata"]).get("program")
            except json.JSONDecodeError:
                prev_program = None
        provider = (
            get_provider(
                agent["model_provider"], agent["model_name"], config.get("api_key")
            )
            if booth_pipeline.has_api_key(config)
            else None
        )
        history = [{"role": r["role"], "content": r["content"]} for r in prior[:-1]]
        result = booth_pipeline.run(
            provider, agent["data_source_id"], payload.content, history, prev_program
        )
        empty = {"nodes": [], "edges": []}
        metadata = {
            "traversal": empty,
            "artifact": result["artifact"],
            "program": result["program"],
        }
        conn = connect()
        conn.execute(
            "INSERT INTO messages (session_id, role, content, metadata) "
            "VALUES (?, 'assistant', ?, ?)",
            (session_id, result["content"], json.dumps(metadata)),
        )
        conn.commit()
        conn.close()
        return {
            "content": result["content"],
            "traversal": empty,
            "artifact": result["artifact"],
        }

    conn.close()

    grounding = _ontology_context(request, payload.content, agent["show_project_id"])
    system = _build_system(config, grounding)

    messages = [{"role": r["role"], "content": r["content"]} for r in prior]
    provider = get_provider(
        agent["model_provider"], agent["model_name"], config.get("api_key")
    )
    try:
        reply = provider.complete(system, messages)
    except Exception as exc:
        raise HTTPException(502, f"LLM provider error: {exc}")

    content, artifact = extract_artifact(reply)
    metadata = {"traversal": grounding["traversal"], "artifact": artifact}
    conn = connect()
    conn.execute(
        "INSERT INTO messages (session_id, role, content, metadata) "
        "VALUES (?, 'assistant', ?, ?)",
        (session_id, content, json.dumps(metadata)),
    )
    conn.commit()
    conn.close()
    return {
        "content": content,
        "traversal": grounding["traversal"],
        "artifact": artifact,
    }
