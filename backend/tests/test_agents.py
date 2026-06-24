def test_agent_crud(auth, project):
    created = auth.post(
        "/api/agents",
        json={"name": "Booth Planner", "type": "standard", "show_project_id": project},
    )
    assert created.status_code == 201
    aid = created.json()["id"]
    assert created.json()["name"] == "Booth Planner"
    assert created.json()["show_project_id"] == project

    patched = auth.patch(
        f"/api/agents/{aid}",
        json={
            "model_provider": "claude",
            "model_name": "claude-opus-4-8",
            "config": {"ontology_instructions": "be helpful"},
        },
    ).json()
    assert patched["model_provider"] == "claude"
    assert patched["config"]["ontology_instructions"] == "be helpful"

    got = auth.get(f"/api/agents/{aid}").json()
    assert got["model_name"] == "claude-opus-4-8"

    assert any(a["id"] == aid for a in auth.get("/api/agents").json())
    # Scoped listing returns the agent for its project and excludes others.
    scoped = auth.get(f"/api/agents?project_id={project}").json()
    assert any(a["id"] == aid for a in scoped)

    assert auth.delete(f"/api/agents/{aid}").status_code == 204
    assert auth.get(f"/api/agents/{aid}").status_code == 404


def test_create_agent_requires_valid_project(auth):
    assert auth.post(
        "/api/agents", json={"name": "Orphan", "show_project_id": 999999}
    ).status_code == 404
    # show_project_id is required
    assert auth.post("/api/agents", json={"name": "Orphan"}).status_code == 422


def test_agent_not_found(auth):
    assert auth.get("/api/agents/999999").status_code == 404
    assert auth.patch("/api/agents/999999", json={"name": "x"}).status_code == 404
    assert auth.delete("/api/agents/999999").status_code == 404


def test_api_key_hidden_in_list_visible_in_get(auth, project):
    aid = auth.post(
        "/api/agents", json={"name": "Keyed", "show_project_id": project}
    ).json()["id"]
    auth.patch(f"/api/agents/{aid}", json={"config": {"api_key": "sk-secret"}})

    listed = next(a for a in auth.get("/api/agents").json() if a["id"] == aid)
    assert "api_key" not in listed["config"]

    got = auth.get(f"/api/agents/{aid}").json()
    assert got["config"]["api_key"] == "sk-secret"
