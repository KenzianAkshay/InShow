import csv
import io
import json
import os
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile

from app.auth import require_user
from app.db import DATABASE_PATH, connect
from app.ontology import build_graph, infer_combined_ontology, read_ontology

DATA_DIR = Path(
    os.getenv("DATA_DIR") or Path(DATABASE_PATH).resolve().parent / "uploads"
)

router = APIRouter(prefix="/api", dependencies=[Depends(require_user)])


def _sheet_to_records(ws) -> list[dict]:
    rows = ws.iter_rows(values_only=True)
    try:
        header = next(rows)
    except StopIteration:
        return []
    headers = [str(h) if h is not None else f"col{i}" for i, h in enumerate(header)]
    records = []
    for row in rows:
        if all(c is None for c in row):
            continue
        # Coerce all cells to strings, matching CSV behaviour and keeping Neo4j
        # property types simple (no datetime objects).
        records.append(
            {
                headers[i]: "" if val is None else str(val)
                for i, val in enumerate(row)
                if i < len(headers)
            }
        )
    return records


def _parse_xlsx_sheets(content: bytes) -> dict[str, list[dict]]:
    """Every non-empty worksheet/tab becomes its own record set, keyed by tab
    name. The ontology builder combines them into one graph."""
    from openpyxl import load_workbook

    wb = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    sheets: dict[str, list[dict]] = {}
    for ws in wb.worksheets:
        records = _sheet_to_records(ws)
        if records:
            sheets[ws.title] = records
    return sheets


def parse_sheets(content: bytes, filename: str) -> dict[str, list[dict]]:
    """Parse a data source into one or more named record sets. Excel workbooks
    yield one set per tab; CSV/JSON yield a single set named after the file."""
    name = (filename or "").lower()
    stem = Path(filename or "data").stem or "data"
    if name.endswith((".xlsx", ".xlsm")):
        sheets = _parse_xlsx_sheets(content)
    elif name.endswith(".json"):
        data = json.loads(content.decode("utf-8-sig"))
        if isinstance(data, dict):
            data = [data]
        sheets = {stem: [d for d in data if isinstance(d, dict)]}
    elif name.endswith(".csv"):
        sheets = {stem: list(csv.DictReader(io.StringIO(content.decode("utf-8-sig"))))}
    else:
        raise HTTPException(400, "Unsupported file type; use .csv, .json, or .xlsx")
    sheets = {k: v for k, v in sheets.items() if v}
    if not sheets:
        raise HTTPException(400, "No records found in file")
    return sheets


def parse_records(content: bytes, filename: str) -> list[dict]:
    """Flat view of every record across all tabs (used for record counts)."""
    return [r for records in parse_sheets(content, filename).values() for r in records]


def _neo4j(request: Request):
    driver = request.app.state.neo4j
    try:
        driver.verify_connectivity()
    except Exception:
        raise HTTPException(503, "Neo4j is not available")
    return driver


@router.get("/data-sources")
def list_data_sources(project_id: int | None = None):
    conn = connect()
    if project_id is None:
        rows = conn.execute(
            "SELECT * FROM data_sources ORDER BY created_at DESC"
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM data_sources WHERE show_project_id = ? "
            "ORDER BY created_at DESC",
            (project_id,),
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@router.get("/data-sources/{source_id}")
def get_data_source(source_id: int):
    conn = connect()
    row = conn.execute(
        "SELECT * FROM data_sources WHERE id = ?", (source_id,)
    ).fetchone()
    conn.close()
    if row is None:
        raise HTTPException(404, "Data source not found")
    return dict(row)


@router.post("/data-sources", status_code=201)
async def create_data_source(
    project_id: int, file: UploadFile = File(...)
):
    content = await file.read()
    records = parse_records(content, file.filename or "data")
    ext = (file.filename or "").rsplit(".", 1)[-1].lower()

    conn = connect()
    if conn.execute(
        "SELECT 1 FROM show_projects WHERE id = ?", (project_id,)
    ).fetchone() is None:
        conn.close()
        raise HTTPException(404, "Show project not found")
    cur = conn.execute(
        "INSERT INTO data_sources (name, type, status, show_project_id) "
        "VALUES (?, ?, ?, ?)",
        (file.filename or "data", ext, "ingested", project_id),
    )
    source_id = cur.lastrowid
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = DATA_DIR / f"{source_id}_{file.filename or 'data'}"
    path.write_bytes(content)
    conn.execute(
        "UPDATE data_sources SET location = ? WHERE id = ?",
        (str(path), source_id),
    )
    conn.commit()
    row = conn.execute(
        "SELECT * FROM data_sources WHERE id = ?", (source_id,)
    ).fetchone()
    conn.close()
    return {**dict(row), "records": len(records)}


@router.post("/data-sources/{source_id}/build")
def build_ontology(source_id: int, request: Request):
    conn = connect()
    row = conn.execute(
        "SELECT * FROM data_sources WHERE id = ?", (source_id,)
    ).fetchone()
    conn.close()
    if row is None:
        raise HTTPException(404, "Data source not found")
    if not row["location"] or not Path(row["location"]).exists():
        raise HTTPException(400, "Data source file is missing")

    content = Path(row["location"]).read_bytes()
    sheets = parse_sheets(content, row["name"])
    spec = infer_combined_ontology(sheets, Path(row["name"]).stem)

    driver = _neo4j(request)
    summary = build_graph(driver, spec, source_id, row["show_project_id"])

    conn = connect()
    conn.execute(
        "UPDATE data_sources SET status = 'in_graph' WHERE id = ?", (source_id,)
    )
    conn.commit()
    conn.close()
    return summary


@router.get("/ontology")
def get_ontology(request: Request, project_id: int):
    return read_ontology(_neo4j(request), project_id)
