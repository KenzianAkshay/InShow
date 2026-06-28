"""Tests for the Booth Layout pipeline (app/booth_pipeline.py) and its chat hook.

These run without any LLM API key (conftest pops them), exercising the
deterministic Synthesise/Explain fallbacks.
"""

import io

from app import booth_pipeline as bp

EMPTY_CATALOG = {"by_kind": {}, "booth_meta": None}


def _kinds(program):
    return {z["kind"]: z.get("count", 1) for z in program["zones"]}


def test_keyword_synthesise_parses_dims_type_and_zones():
    msg = "Plan a 6x4 corner booth with a reception, 2 demo stations, a meeting room and storage"
    program = bp.synthesise(None, msg, [], None, EMPTY_CATALOG)
    assert program["booth"]["width"] == 6.0
    assert program["booth"]["depth"] == 4.0
    assert program["booth"]["type"] == "corner"
    kinds = _kinds(program)
    assert kinds.get("reception") == 1
    assert kinds.get("demo") == 2
    assert kinds.get("meeting") == 1
    assert kinds.get("storage") == 1


def test_defaults_when_nothing_specified():
    program = bp.synthesise(None, "design my booth please", [], None, EMPTY_CATALOG)
    assert program["zones"]  # falls back to a sensible default set
    assert program["booth"]["width"] > 0 and program["booth"]["depth"] > 0


def test_iteration_add_a_demo_station():
    base = bp.synthesise(None, "8x6 island with a reception and 2 demo stations",
                         [], None, EMPTY_CATALOG)
    nxt = bp.synthesise(None, "add a demo station", [], base, EMPTY_CATALOG)
    demos = sum(z.get("count", 1) for z in nxt["zones"] if z["kind"] == "demo")
    assert demos == 3
    # Booth footprint is carried over from the prior program.
    assert nxt["booth"]["type"] == "island"


def test_iteration_move_to_the_back_lowers_priority():
    base = bp.synthesise(None, "6x4 booth with a reception and a meeting room",
                         [], None, EMPTY_CATALOG)
    nxt = bp.synthesise(None, "move the meeting room to the back", [], base, EMPTY_CATALOG)
    meeting = [z for z in nxt["zones"] if z["kind"] == "meeting"][0]
    assert meeting["priority"] <= 1


def test_iteration_remove_zone():
    base = bp.synthesise(None, "6x4 booth with a reception, a meeting room and storage",
                         [], None, EMPTY_CATALOG)
    nxt = bp.synthesise(None, "remove the storage", [], base, EMPTY_CATALOG)
    assert "storage" not in _kinds(nxt)


def test_catalog_sizes_applied_to_zones():
    catalog = {"by_kind": {"demo": {"w": 1.8, "d": 1.2, "height": 1.3}}, "booth_meta": None}
    program = bp.synthesise(None, "6x4 booth with 2 demo stations", [], None, catalog)
    demo = [z for z in program["zones"] if z["kind"] == "demo"][0]
    assert demo["w"] == 1.8 and demo["d"] == 1.2


def test_run_greets_politely():
    out = bp.run(None, None, "hello", [], None)
    assert out["artifact"] is None
    assert "Hello" in out["content"]
    assert "booth" in out["content"].lower() or "stand" in out["content"].lower()


def test_run_asks_when_goals_missing():
    out = bp.run(None, None, "help me design my booth", [], None)
    assert out["artifact"] is None
    assert out["program"].get("_draft") is True
    assert "•" in out["content"]  # lists the missing goals


def test_run_plans_after_goals_provided():
    first = bp.run(None, None, "design my booth", [], None)
    assert first["artifact"] is None
    second = bp.run(
        None, None, "6x4 corner with a reception and 2 demo stations", [], first["program"]
    )
    assert second["artifact"] and second["artifact"]["type"] == "booth_layout"
    assert second["program"]["booth"]["type"] == "corner"


def test_run_accumulates_goals_across_turns():
    s1 = bp.run(None, None, "plan a 6x4 booth", [], None)
    assert s1["artifact"] is None and s1["program"]["dims"] == [6.0, 4.0]
    s2 = bp.run(
        None, None, "make it a corner with a reception and 2 demo stations", [], s1["program"]
    )
    assert s2["artifact"]["type"] == "booth_layout"
    assert s2["program"]["booth"]["width"] == 6.0


def test_run_produces_valid_booth_artifact_without_llm():
    out = bp.run(
        None, None,
        "Plan a 6x4 corner booth with a reception, 2 demo stations, a meeting room and storage",
        [], None,
    )
    art = out["artifact"]
    assert art["type"] == "booth_layout"
    assert art["validation"]["ok"] is True
    assert len(art["zones"]) >= 4
    assert isinstance(out["content"], str) and out["content"]
    assert out["program"]["booth"]["type"] == "corner"


# --------------------------------------------------------------------------- #
# Catalog reading + chat integration through the API
# --------------------------------------------------------------------------- #
CATALOG_CSV = (
    "name,category,width,depth,height\n"
    "Reception desk,reception,2.5,1.2,1.1\n"
    "Demo pod,demo,1.8,1.2,1.2\n"
    "Meeting room,meeting,3.0,2.5,2.4\n"
    "Storage unit,storage,1.5,1.5,2.2\n"
)


def _upload_catalog(auth, project) -> int:
    r = auth.post(
        f"/api/data-sources?project_id={project}",
        files={"file": ("booth_elements.csv", io.BytesIO(CATALOG_CSV.encode()), "text/csv")},
    )
    assert r.status_code in (200, 201), r.text
    return r.json()["id"]


def test_read_catalog_maps_columns(auth, project):
    source_id = _upload_catalog(auth, project)
    catalog = bp.read_catalog(source_id)
    assert "demo" in catalog["by_kind"]
    assert catalog["by_kind"]["demo"]["w"] == 1.8
    assert "meeting" in catalog["by_kind"]


def test_booth_layout_chat_returns_layout_artifact(auth, project):
    source_id = _upload_catalog(auth, project)
    r = auth.post(
        "/api/agents",
        json={"name": "Stand Planner", "type": "booth_layout", "show_project_id": project},
    )
    assert r.status_code == 201
    agent_id = r.json()["id"]
    auth.patch(f"/api/agents/{agent_id}", json={"data_source_id": source_id})

    r = auth.post(
        f"/api/agents/{agent_id}/chat",
        json={"content": "Plan a 6x4 corner booth with a reception, 2 demo stations, a meeting room and storage"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    art = body["artifact"]
    assert art and art["type"] == "booth_layout"
    assert art["validation"]["ok"] is True
    assert len(art["zones"]) >= 4
    # The requested zone kinds are present (sizes may be scaled to fit the booth).
    assert any(z["kind"] == "demo" for z in art["zones"])
    assert any(z["kind"] == "reception" for z in art["zones"])


def test_booth_layout_iteration_persists_program(auth, project):
    r = auth.post(
        "/api/agents",
        json={"name": "Planner 2", "type": "booth_layout", "show_project_id": project},
    )
    agent_id = r.json()["id"]
    auth.post(f"/api/agents/{agent_id}/chat", json={"content": "6x4 corner booth with a reception and 2 demo stations"})
    r2 = auth.post(f"/api/agents/{agent_id}/chat", json={"content": "add a demo station"})
    art = r2.json()["artifact"]
    demos = [z for z in art["zones"] if z["kind"] == "demo"]
    assert len(demos) == 3
