import json

import app.ontology_agent as oa
from app.llm import LLMProvider

CSV = "exhibitor,booth,city,stage\nAcme,A12,Berlin,Won\nGlobex,B07,Munich,Lost\n"
MAPPING = {
    "classes": [
        {"name": "Exhibitor", "key_column": "exhibitor", "property_columns": ["booth"]},
        {"name": "City", "key_column": "city"},
        {"name": "Stage", "key_column": "stage"},
    ],
    "relationships": [{"name": "LOCATED_IN", "from": "Exhibitor", "to": "City"}],
}


class _Schema(LLMProvider):
    calls = 0

    def complete(self, system, messages):
        _Schema.calls += 1
        return "schema: " + json.dumps(MAPPING)


def test_build_with_agent_uses_two_llm_calls():
    _Schema.calls = 0
    rows = [{"exhibitor": "Acme", "booth": "A12", "city": "Berlin", "stage": "Won"}]
    spec = oa.build_with_agent(_Schema(), {"exhibitors": rows}, "exhibitors")
    assert _Schema.calls == 2  # propose + evaluate/refine for the one tab
    assert "Exhibitor:Acme" in {n["uid"] for n in spec["nodes"]}


def test_build_with_agent_combines_multiple_tabs():
    _Schema.calls = 0
    sheets = {
        "Exhibitors": [{"exhibitor": "Acme", "booth": "A12", "city": "Berlin", "stage": "Won"}],
        "Sessions": [{"exhibitor": "Acme", "booth": "B01", "city": "Berlin", "stage": "Lost"}],
    }
    spec = oa.build_with_agent(_Schema(), sheets, "expo")
    assert _Schema.calls == 4  # two tabs x (propose + refine)
    # The shared City:Berlin from both tabs collapses into one node.
    assert sum(1 for n in spec["nodes"] if n["uid"] == "City:Berlin") == 1


def _upload(auth, project):
    return auth.post(
        f"/api/data-sources?project_id={project}",
        files={"file": ("e.csv", CSV, "text/csv")},
    ).json()["id"]


def test_agent_build_llm_path(auth_up, project, monkeypatch):
    monkeypatch.setattr(oa, "get_provider", lambda *a, **k: _Schema())
    aid = auth_up.post(
        "/api/agents",
        json={"name": "B", "type": "ontology_creation", "show_project_id": project},
    ).json()["id"]
    auth_up.patch(f"/api/agents/{aid}", json={"config": {"api_key": "sk-x"}})
    sid = _upload(auth_up, project)
    r = auth_up.post(f"/api/agents/{aid}/build", json={"data_source_id": sid})
    assert r.status_code == 200
    assert r.json()["method"] == "agent"
    assert r.json()["nodes"] > 0


def test_agent_build_standard_is_deterministic(auth_up, project):
    aid = auth_up.post(
        "/api/agents",
        json={"name": "S", "type": "standard", "show_project_id": project},
    ).json()["id"]
    sid = _upload(auth_up, project)
    r = auth_up.post(f"/api/agents/{aid}/build", json={"data_source_id": sid})
    assert r.status_code == 200
    assert r.json()["method"] == "deterministic"


def test_agent_build_errors(auth_up, project):
    nid = auth_up.post(
        "/api/agents",
        json={"name": "N", "type": "ontology_creation", "show_project_id": project},
    ).json()["id"]
    assert auth_up.post(f"/api/agents/{nid}/build", json={}).status_code == 400
    sid = _upload(auth_up, project)
    assert auth_up.post(
        "/api/agents/999999/build", json={"data_source_id": sid}
    ).status_code == 404
