def test_projects_require_auth(client):
    assert client.get("/api/projects").status_code == 401


def test_project_crud(auth):
    created = auth.post(
        "/api/projects", json={"name": "CES 2026", "description": "Vegas"}
    )
    assert created.status_code == 201
    pid = created.json()["id"]
    assert created.json()["name"] == "CES 2026"

    assert any(p["id"] == pid for p in auth.get("/api/projects").json())
    assert auth.get(f"/api/projects/{pid}").json()["description"] == "Vegas"

    patched = auth.patch(
        f"/api/projects/{pid}", json={"name": "CES 2027"}
    ).json()
    assert patched["name"] == "CES 2027"

    assert auth.delete(f"/api/projects/{pid}").status_code == 204
    assert auth.get(f"/api/projects/{pid}").status_code == 404


def test_project_requires_name(auth):
    assert auth.post("/api/projects", json={"name": "  "}).status_code == 400


def test_project_lists_agent_count(auth):
    pid = auth.post("/api/projects", json={"name": "Show"}).json()["id"]
    auth.post("/api/agents", json={"name": "A", "show_project_id": pid})
    auth.post("/api/agents", json={"name": "B", "show_project_id": pid})
    listed = next(p for p in auth.get("/api/projects").json() if p["id"] == pid)
    assert listed["agent_count"] == 2


def test_deleting_project_cascades_agents(auth):
    pid = auth.post("/api/projects", json={"name": "Temp"}).json()["id"]
    aid = auth.post(
        "/api/agents", json={"name": "A", "show_project_id": pid}
    ).json()["id"]
    assert auth.delete(f"/api/projects/{pid}").status_code == 204
    assert auth.get(f"/api/agents/{aid}").status_code == 404
