import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.auth import require_user
from app.db import connect

router = APIRouter(prefix="/api", dependencies=[Depends(require_user)])


class AgentCreate(BaseModel):
    name: str
    type: str = "standard"
    show_project_id: int


class AgentUpdate(BaseModel):
    name: str | None = None
    type: str | None = None
    model_provider: str | None = None
    model_name: str | None = None
    config: dict | None = None
    data_source_id: int | None = None


def _row_to_agent(row, include_secret: bool = False) -> dict:
    agent = dict(row)
    agent["config"] = json.loads(agent["config"])
    if not include_secret and "api_key" in agent["config"]:
        # Don't expose the stored key in list/create responses.
        agent["config"] = {k: v for k, v in agent["config"].items() if k != "api_key"}
    return agent


@router.get("/agents")
def list_agents(project_id: int | None = None):
    conn = connect()
    if project_id is None:
        rows = conn.execute(
            "SELECT * FROM agents ORDER BY created_at DESC"
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM agents WHERE show_project_id = ? ORDER BY created_at DESC",
            (project_id,),
        ).fetchall()
    conn.close()
    return [_row_to_agent(r) for r in rows]


@router.post("/agents", status_code=201)
def create_agent(payload: AgentCreate):
    conn = connect()
    if conn.execute(
        "SELECT 1 FROM show_projects WHERE id = ?", (payload.show_project_id,)
    ).fetchone() is None:
        conn.close()
        raise HTTPException(status_code=404, detail="Show project not found")
    cur = conn.execute(
        "INSERT INTO agents (name, type, show_project_id) VALUES (?, ?, ?)",
        (payload.name, payload.type, payload.show_project_id),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM agents WHERE id = ?", (cur.lastrowid,)).fetchone()
    conn.close()
    return _row_to_agent(row)


@router.get("/agents/{agent_id}")
def get_agent(agent_id: int):
    conn = connect()
    row = conn.execute("SELECT * FROM agents WHERE id = ?", (agent_id,)).fetchone()
    conn.close()
    if row is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    return _row_to_agent(row, include_secret=True)


@router.patch("/agents/{agent_id}")
def update_agent(agent_id: int, payload: AgentUpdate):
    fields = payload.model_dump(exclude_unset=True)
    if "config" in fields:
        fields["config"] = json.dumps(fields["config"])

    conn = connect()
    if conn.execute("SELECT 1 FROM agents WHERE id = ?", (agent_id,)).fetchone() is None:
        conn.close()
        raise HTTPException(status_code=404, detail="Agent not found")

    if fields:
        assignments = ", ".join(f"{key} = ?" for key in fields)
        conn.execute(
            f"UPDATE agents SET {assignments}, updated_at = datetime('now') WHERE id = ?",
            (*fields.values(), agent_id),
        )
        conn.commit()
    row = conn.execute("SELECT * FROM agents WHERE id = ?", (agent_id,)).fetchone()
    conn.close()
    return _row_to_agent(row, include_secret=True)


@router.delete("/agents/{agent_id}", status_code=204)
def delete_agent(agent_id: int):
    conn = connect()
    cur = conn.execute("DELETE FROM agents WHERE id = ?", (agent_id,))
    conn.commit()
    conn.close()
    if cur.rowcount == 0:
        raise HTTPException(status_code=404, detail="Agent not found")
