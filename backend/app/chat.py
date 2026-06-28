import json
import os
import re

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app import analytics, booth_pipeline, conversation
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
    "what the ontology does cover. Do not speculate or generalise beyond the data. "
    "You MAY count, aggregate, and compute over this data — that is grounded "
    "analysis, not speculation."
)

ANALYTICS_GUIDE = (
    "You have tools for quantitative work: `query_ontology` runs exact "
    "aggregations over this project's data (counts per class, group-by a "
    "dimension, totals, numeric sum/average/min/max), and `calculate` evaluates "
    "arithmetic exactly. ALWAYS use these tools for numbers and math rather than "
    "computing in your head, then present the results — and when a chart, table, "
    "or metric makes the answer clearer, append the canvas block described below."
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

ASK_AGENT_TOOL = {
    "name": "ask_agent",
    "description": (
        "Consult another agent in THIS project by name and get its answer. Use "
        "when another agent's specialty (e.g. booth layout, a specific data "
        "domain) fits part of the question. Synthesise its answer into your reply "
        "and name the agent you consulted."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "agent": {"type": "string", "description": "the other agent's exact name"},
            "question": {"type": "string", "description": "what to ask that agent"},
        },
        "required": ["agent", "question"],
    },
}

AGENTS_GUIDE = (
    "Other agents in this project can help with their specialties. Consult one "
    "with the `ask_agent` tool when its focus fits part of the question, then "
    "weave its answer into yours and name the agent you asked. Available agents:\n"
)


def _type_label(t: str) -> str:
    return {
        "ontology_creation": "ontology builder",
        "booth_layout": "booth layout planner",
    }.get(t, "general analyst")


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


def _has_key(config: dict) -> bool:
    return bool(config.get("api_key")) or bool(
        os.getenv("ANTHROPIC_API_KEY") or os.getenv("OPENAI_API_KEY")
    )


def _deterministic(request: Request, project_id: int, query: str) -> dict | None:
    """Compute a chart/aggregation answer with no LLM (used when no API key is
    configured, or as a fallback when the provider errors)."""
    try:
        driver = request.app.state.neo4j
        driver.verify_connectivity()
        return analytics.deterministic_analytics(driver, project_id, query)
    except Exception:
        return None


def _suggest(request: Request, project_id: int, query: str) -> list[str]:
    """Ontology-grounded, intent-aware next-question suggestions (best-effort)."""
    try:
        driver = request.app.state.neo4j
        driver.verify_connectivity()
        return analytics.suggest_followups(driver, project_id, query)
    except Exception:
        return []


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


def _build_system(config: dict, grounding: dict, peers: list | None = None) -> str:
    """Assemble a strictly-grounded system prompt: the agent may only use the
    project's ontology and ingested data, never outside knowledge."""
    # An operator-supplied system prompt sets the agent's persona/behavior; the
    # platform's grounding and analytics rules are always appended after it.
    system = (
        config.get("system_prompt")
        or "You are a ShowSphere exhibitor-services agent for trade shows."
    )
    system += (
        "\n\nBe warm and courteous: greet the user, respond briefly to small talk, "
        "and keep a polite, professional tone throughout."
    )
    if config.get("ontology_instructions"):
        system += "\n\n" + config["ontology_instructions"]
    system += "\n\n" + GROUNDING_RULES
    system += "\n\n" + ANALYTICS_GUIDE

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

    if peers:
        roster = "\n".join(
            f"- {p['name']} ({_type_label(p['type'])})"
            + (f": {_peer_note(p)}" if _peer_note(p) else "")
            for p in peers
        )
        system += "\n\n" + AGENTS_GUIDE + roster

    system += "\n\n" + CANVAS_GUIDE
    return system


def _peer_note(peer: dict) -> str:
    try:
        cfg = peer["config"]
        cfg = json.loads(cfg) if isinstance(cfg, str) else (cfg or {})
        return str(cfg.get("ontology_instructions", ""))[:80]
    except Exception:
        return ""


def _agent_config(row) -> dict:
    cfg = row["config"]
    return json.loads(cfg) if isinstance(cfg, str) else (cfg or {})


def _peers(project_id, exclude_id: int) -> list[dict]:
    """Other agents in the same project (potential delegates)."""
    if project_id is None:
        return []
    conn = connect()
    rows = conn.execute(
        "SELECT * FROM agents WHERE show_project_id = ? AND id != ? ORDER BY created_at",
        (project_id, exclude_id),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def _find_sibling(project_id, name: str, exclude_id: int):
    conn = connect()
    row = conn.execute(
        "SELECT * FROM agents WHERE show_project_id = ? AND id != ? "
        "AND lower(name) = lower(?)",
        (project_id, exclude_id, (name or "").strip()),
    ).fetchone()
    conn.close()
    return row


def _addressed_sibling(peers: list[dict], query: str):
    """When no LLM is configured, route to a sibling the user explicitly names
    with a delegation verb (e.g. 'ask Stats how many ...')."""
    low = f" {query.lower()} "
    if not any(v in low for v in [" ask ", "consult", "delegate", "check with", " agent "]):
        return None
    for p in peers:
        if p["name"].lower() in low:
            return p
    return None


def run_subagent(request: Request, agent_row, question: str) -> dict:
    """Run one sibling agent on a question and return {content, artifact}. The
    sub-agent uses its own grounding/tools (or the booth pipeline) but cannot
    delegate further — delegation is capped at one level to prevent recursion."""
    config = _agent_config(agent_row)
    if agent_row["type"] == "booth_layout":
        provider = (
            get_provider(
                agent_row["model_provider"], agent_row["model_name"], config.get("api_key")
            )
            if _has_key(config)
            else None
        )
        try:
            res = booth_pipeline.run(
                provider, agent_row["data_source_id"], question, [], None
            )
            return {"content": res["content"], "artifact": res["artifact"]}
        except Exception:
            return {"content": "(could not produce a booth layout)", "artifact": None}

    project_id = agent_row["show_project_id"]
    grounding = _ontology_context(request, question, project_id)
    system = _build_system(config, grounding)  # no peers -> no further delegation
    if _has_key(config):
        try:
            provider = get_provider(
                agent_row["model_provider"], agent_row["model_name"], config.get("api_key")
            )
            dispatch = analytics.make_dispatch(request.app.state.neo4j, project_id)
            reply = provider.complete_with_tools(
                system, [{"role": "user", "content": question}], analytics.TOOLS, dispatch
            )
            content, artifact = extract_artifact(reply)
            return {"content": content, "artifact": artifact}
        except Exception:
            pass
    det = _deterministic(request, project_id, question)
    if det is not None:
        return det
    return {
        "content": "I don't have enough data in this project to answer that.",
        "artifact": None,
    }


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


@router.delete("/agents/{agent_id}/messages", status_code=204)
def clear_messages(agent_id: int):
    """Clear an agent's chat history (all messages across its sessions)."""
    conn = connect()
    agent = conn.execute(
        "SELECT id FROM agents WHERE id = ?", (agent_id,)
    ).fetchone()
    if agent is None:
        conn.close()
        raise HTTPException(404, "Agent not found")
    conn.execute(
        "DELETE FROM messages WHERE session_id IN "
        "(SELECT id FROM chat_sessions WHERE agent_id = ?)",
        (agent_id,),
    )
    conn.commit()
    conn.close()


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
        suggestions = result.get("suggestions") or []
        metadata = {
            "traversal": empty,
            "artifact": result["artifact"],
            "program": result["program"],
            "suggestions": suggestions,
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
            "suggestions": suggestions,
        }

    conn.close()

    project_id = agent["show_project_id"]
    peers = _peers(project_id, agent_id)
    grounding = _ontology_context(request, payload.content, project_id)
    system = _build_system(config, grounding, peers)
    messages = [{"role": r["role"], "content": r["content"]} for r in prior]

    if _has_key(config):
        provider = get_provider(
            agent["model_provider"], agent["model_name"], config.get("api_key")
        )
        base_dispatch = analytics.make_dispatch(request.app.state.neo4j, project_id)

        def dispatch(name: str, args: dict) -> dict:
            if name == "ask_agent":
                sib = _find_sibling(project_id, str(args.get("agent", "")), agent_id)
                if sib is None:
                    return {"error": f"no agent named '{args.get('agent', '')}' in this project"}
                sub = run_subagent(request, sib, str(args.get("question", "")))
                return {"agent": sib["name"], "answer": sub["content"]}
            return base_dispatch(name, args)

        tools = analytics.TOOLS + ([ASK_AGENT_TOOL] if peers else [])
        try:
            reply = provider.complete_with_tools(system, messages, tools, dispatch)
            content, artifact = extract_artifact(reply)
        except Exception as exc:
            # Degrade gracefully: try a deterministic analytic answer, then a
            # polite social reply, before erroring.
            det = _deterministic(request, project_id, payload.content)
            if det is not None:
                content, artifact = det["content"], det["artifact"]
            else:
                social = conversation.social_reply(payload.content)
                if social is None:
                    raise HTTPException(502, f"LLM provider error: {exc}")
                content, artifact = social, None
    else:
        # No language model configured. Delegation > analytics > greetings > hint.
        sib = _addressed_sibling(peers, payload.content)
        det = None if sib is not None else _deterministic(request, project_id, payload.content)
        if sib is not None:
            sub = run_subagent(request, sib, payload.content)
            content = f"I consulted **{sib['name']}** — {sub['content']}"
            artifact = sub["artifact"]
        elif det is not None:
            content, artifact = det["content"], det["artifact"]
        elif conversation.social_reply(payload.content) is not None:
            content, artifact = conversation.social_reply(payload.content), None
        else:
            hint = (
                f' or ask another agent, e.g. "ask {peers[0]["name"]} ..."'
                if peers
                else ""
            )
            content, artifact = (
                "Happy to help! I work over this project's ingested data — try a "
                'request like "chart exhibitors by city" or "how many sponsors"'
                + hint + ".",
                None,
            )

    # Recommend next questions, grounded in the ontology and the user's intent.
    suggestions = _suggest(request, project_id, payload.content)
    metadata = {
        "traversal": grounding["traversal"],
        "artifact": artifact,
        "suggestions": suggestions,
    }
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
        "suggestions": suggestions,
    }
