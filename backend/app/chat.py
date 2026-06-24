import json
import re

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.auth import require_user
from app.db import connect
from app.llm import get_provider
from app.ontology import retrieve_context

router = APIRouter(prefix="/api", dependencies=[Depends(require_user)])

ARTIFACT_TYPES = {"bar", "line", "table", "metrics", "map"}
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
    try:
        driver = request.app.state.neo4j
        driver.verify_connectivity()
        return retrieve_context(driver, query, project_id)
    except Exception:
        return {"context": "", "traversal": {"nodes": [], "edges": []}}


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
    conn.close()

    grounding = _ontology_context(request, payload.content, agent["show_project_id"])
    config = json.loads(agent["config"])
    system = "You are an InShow exhibitor-services agent for trade shows."
    if config.get("ontology_instructions"):
        system += "\n\n" + config["ontology_instructions"]
    if grounding["context"]:
        system += "\n\nRelevant ontology context:\n" + grounding["context"]
    system += "\n\n" + CANVAS_GUIDE

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
