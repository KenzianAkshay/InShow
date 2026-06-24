import hashlib
import os
import sqlite3
from pathlib import Path

DATABASE_PATH = os.getenv("DATABASE_PATH", "inshow.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS show_projects (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS data_sources (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL,
    type            TEXT NOT NULL,
    location        TEXT,
    status          TEXT NOT NULL DEFAULT 'new',
    show_project_id INTEGER REFERENCES show_projects(id) ON DELETE CASCADE,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS agents (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL,
    type            TEXT NOT NULL DEFAULT 'standard',
    model_provider  TEXT,
    model_name      TEXT,
    config          TEXT NOT NULL DEFAULT '{}',
    data_source_id  INTEGER REFERENCES data_sources(id) ON DELETE SET NULL,
    show_project_id INTEGER REFERENCES show_projects(id) ON DELETE CASCADE,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS chat_sessions (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id   INTEGER NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    user_id    INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS messages (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    role       TEXT NOT NULL,
    content    TEXT NOT NULL,
    metadata   TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _column_names(conn, table: str) -> set[str]:
    return {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}


def _migrate(conn) -> None:
    """Bring an older database forward to the Show Project model: add the
    show_project_id columns, then file any orphaned agents/data sources under a
    single 'Default Show' project so existing data stays reachable."""
    agent_cols = _column_names(conn, "agents")
    source_cols = _column_names(conn, "data_sources")
    if "show_project_id" not in agent_cols:
        conn.execute("ALTER TABLE agents ADD COLUMN show_project_id INTEGER")
    if "show_project_id" not in source_cols:
        conn.execute("ALTER TABLE data_sources ADD COLUMN show_project_id INTEGER")

    orphan_agents = conn.execute(
        "SELECT COUNT(*) AS n FROM agents WHERE show_project_id IS NULL"
    ).fetchone()["n"]
    orphan_sources = conn.execute(
        "SELECT COUNT(*) AS n FROM data_sources WHERE show_project_id IS NULL"
    ).fetchone()["n"]
    if orphan_agents == 0 and orphan_sources == 0:
        return

    row = conn.execute(
        "SELECT id FROM show_projects WHERE name = ? ORDER BY id LIMIT 1",
        ("Default Show",),
    ).fetchone()
    if row is None:
        cur = conn.execute(
            "INSERT INTO show_projects (name, description) VALUES (?, ?)",
            ("Default Show", "Migrated agents and data sources."),
        )
        project_id = cur.lastrowid
    else:
        project_id = row["id"]
    conn.execute(
        "UPDATE agents SET show_project_id = ? WHERE show_project_id IS NULL",
        (project_id,),
    )
    conn.execute(
        "UPDATE data_sources SET show_project_id = ? WHERE show_project_id IS NULL",
        (project_id,),
    )


def init_db() -> None:
    Path(DATABASE_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = connect()
    conn.executescript(SCHEMA)
    _migrate(conn)
    if conn.execute("SELECT 1 FROM users WHERE username = ?", ("user",)).fetchone() is None:
        conn.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            ("user", hashlib.sha256(b"password").hexdigest()),
        )
    conn.commit()
    conn.close()
