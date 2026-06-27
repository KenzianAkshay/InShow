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


def test_describe_requires_auth(client):
    assert client.get("/api/projects/1/describe").status_code == 401


def test_describe_project_aggregates_components(auth_up):
    import io

    pid = auth_up.post("/api/projects", json={"name": "Describe Me"}).json()["id"]
    auth_up.post(
        "/api/agents",
        json={"name": "Concierge", "type": "standard", "show_project_id": pid},
    )
    auth_up.post(
        f"/api/data-sources?project_id={pid}",
        files={"file": ("exhibitors.csv", io.BytesIO(b"a,b\n1,2\n"), "text/csv")},
    )

    body = auth_up.get(f"/api/projects/{pid}/describe").json()
    assert body["project"]["name"] == "Describe Me"
    assert len(body["data_sources"]) == 1
    assert body["data_sources"][0]["name"] == "exhibitors.csv"
    assert len(body["agents"]) == 1
    assert body["agents"][0]["name"] == "Concierge"
    # Ontology summary keys are always present (empty under the mock driver).
    assert set(body["ontology"]) == {
        "classes",
        "relations",
        "node_total",
        "relation_total",
    }


def test_describe_lists_excel_tabs_as_separate_sources(auth_up):
    import io

    from openpyxl import Workbook

    pid = auth_up.post("/api/projects", json={"name": "Tabs"}).json()["id"]
    wb = Workbook()
    ws1 = wb.active
    ws1.title = "Exhibitors"
    ws1.append(["exhibitor", "city"])
    ws1.append(["Acme", "Berlin"])
    ws2 = wb.create_sheet("Sessions")
    ws2.append(["session", "city"])
    ws2.append(["Keynote", "Berlin"])
    ws2.append(["Panel", "Munich"])
    buf = io.BytesIO()
    wb.save(buf)
    auth_up.post(
        f"/api/data-sources?project_id={pid}",
        files={
            "file": (
                "expo.xlsx",
                buf.getvalue(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )

    sources = auth_up.get(f"/api/projects/{pid}/describe").json()["data_sources"]
    assert len(sources) == 1
    sheets = {s["name"]: s["records"] for s in sources[0]["sheets"]}
    assert sheets == {"Exhibitors": 1, "Sessions": 2}


def test_describe_missing_project_404(auth):
    assert auth.get("/api/projects/99999/describe").status_code == 404


def test_deleting_project_cascades_agents(auth):
    pid = auth.post("/api/projects", json={"name": "Temp"}).json()["id"]
    aid = auth.post(
        "/api/agents", json={"name": "A", "show_project_id": pid}
    ).json()["id"]
    assert auth.delete(f"/api/projects/{pid}").status_code == 204
    assert auth.get(f"/api/agents/{aid}").status_code == 404
