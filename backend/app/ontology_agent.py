import json
import os
import re

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.auth import require_user
from app.db import connect
from app.ingestion import parse_sheets
from app.llm import LLMProvider, get_provider
from app.ontology import (
    build_graph,
    infer_combined_ontology,
    instantiate_ontology,
    merge_specs,
)
from pathlib import Path

router = APIRouter(prefix="/api", dependencies=[Depends(require_user)])

SYSTEM = (
    "You are the Ontology Creation agent for ShowSphere, a trade-show platform. "
    "You research a dataset, analyse its columns, reason about the entities and "
    "relationships it describes, and design a comprehensive graph data model."
)


def _parse_json(text: str) -> dict | None:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        value = json.loads(match.group(0))
        return value if isinstance(value, dict) else None
    except json.JSONDecodeError:
        return None


def _propose_prompt(columns: list[str], sample: list[dict]) -> str:
    return (
        "Dataset columns: " + ", ".join(columns) + "\n\n"
        "Sample rows (JSON):\n" + json.dumps(sample, indent=2) + "\n\n"
        "Research and analyse this dataset, then design an ontology. Decide which "
        "columns are entities (each becomes a class keyed by that column), which "
        "are properties of an entity, and what relationships connect the entities. "
        "Return ONLY JSON of this exact shape:\n"
        '{"classes":[{"name":"Exhibitor","key_column":"exhibitor",'
        '"property_columns":["booth"]}],'
        '"relationships":[{"name":"LOCATED_IN","from":"Exhibitor","to":"City"}]}'
    )


def _refine_prompt(mapping: dict) -> str:
    return (
        "Here is a proposed ontology:\n" + json.dumps(mapping, indent=2) + "\n\n"
        "Evaluate it for completeness and correctness: are any entities missing, "
        "are relationships sensible and directional, are key_columns valid? "
        "Return ONLY the improved ontology JSON in the same shape."
    )


def build_with_agent(
    provider: LLMProvider, sheets: dict[str, list[dict]], source_name: str
) -> dict:
    """Research -> Analysis/Reasoning (propose) -> Evaluation (refine), run per
    tab and merged into one ontology spanning all tabs."""
    specs: list[dict] = []
    for sheet_name, records in sheets.items():
        if not records:
            continue
        columns = sorted({k for r in records for k in r})
        proposed = _parse_json(provider.complete(SYSTEM, [
            {"role": "user", "content": _propose_prompt(columns, records[:15])}
        ]))
        if not proposed:
            continue
        refined = _parse_json(provider.complete(SYSTEM, [
            {"role": "user", "content": _refine_prompt(proposed)}
        ])) or proposed
        specs.append(instantiate_ontology(refined, records, sheet_name))
    if not specs:
        raise ValueError("Could not parse a schema from the model")
    return merge_specs(specs, source_name)


class BuildRequest(BaseModel):
    data_source_id: int | None = None
    all_columns: bool | None = None


@router.post("/agents/{agent_id}/build")
def agent_build(agent_id: int, payload: BuildRequest, request: Request):
    conn = connect()
    agent = conn.execute("SELECT * FROM agents WHERE id = ?", (agent_id,)).fetchone()
    if agent is None:
        conn.close()
        raise HTTPException(404, "Agent not found")
    source_id = payload.data_source_id or agent["data_source_id"]
    if not source_id:
        conn.close()
        raise HTTPException(400, "No data source selected for this agent")
    source = conn.execute(
        "SELECT * FROM data_sources WHERE id = ?", (source_id,)
    ).fetchone()
    conn.close()
    if source is None:
        raise HTTPException(404, "Data source not found")
    if not source["location"] or not Path(source["location"]).exists():
        raise HTTPException(400, "Data source file is missing")

    sheets = parse_sheets(Path(source["location"]).read_bytes(), source["name"])
    name = Path(source["name"]).stem

    driver = request.app.state.neo4j
    try:
        driver.verify_connectivity()
    except Exception:
        raise HTTPException(503, "Neo4j is not available")

    config = json.loads(agent["config"])
    has_key = bool(config.get("api_key")) or bool(
        os.getenv("ANTHROPIC_API_KEY") or os.getenv("OPENAI_API_KEY")
    )
    # Star-schema toggle: explicit request wins, else the saved agent setting.
    all_columns = (
        payload.all_columns
        if payload.all_columns is not None
        else bool(config.get("all_columns_as_nodes"))
    )
    method = "deterministic"
    if all_columns:
        # "Every column is its own node" is a deterministic structural choice;
        # honour it directly rather than letting the LLM redesign the schema.
        spec = infer_combined_ontology(sheets, name, all_columns=True)
        method = "deterministic-all-columns"
    elif agent["type"] == "ontology_creation" and has_key:
        provider = get_provider(
            agent["model_provider"], agent["model_name"], config.get("api_key")
        )
        try:
            spec = build_with_agent(provider, sheets, name)
            method = "agent"
        except Exception:
            spec = infer_combined_ontology(sheets, name)
            method = "deterministic-fallback"
    else:
        spec = infer_combined_ontology(sheets, name)

    summary = build_graph(driver, spec, source_id, agent["show_project_id"])
    summary["method"] = method

    conn = connect()
    conn.execute(
        "UPDATE data_sources SET status = 'in_graph' WHERE id = ?", (source_id,)
    )
    conn.commit()
    conn.close()
    return summary
