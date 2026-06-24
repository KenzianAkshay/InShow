from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.auth import require_user
from app.db import connect

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
