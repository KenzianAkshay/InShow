CSV = "exhibitor,booth,city\nAcme,A12,Berlin\nGlobex,B07,Munich\n"


def test_upload_csv(auth, project):
    r = auth.post(
        f"/api/data-sources?project_id={project}",
        files={"file": ("x.csv", CSV, "text/csv")},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["records"] == 2
    assert body["type"] == "csv"
    assert body["status"] == "ingested"
    assert body["show_project_id"] == project


def test_upload_json(auth, project):
    data = '[{"a": 1}, {"a": 2}, {"a": 3}]'
    r = auth.post(
        f"/api/data-sources?project_id={project}",
        files={"file": ("x.json", data, "application/json")},
    )
    assert r.status_code == 201
    assert r.json()["records"] == 3


def test_upload_xlsx(auth, project):
    import io

    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.append(["exhibitor", "city", "booths"])
    ws.append(["Acme", "Berlin", 3])
    ws.append(["Globex", "Munich", 5])
    buf = io.BytesIO()
    wb.save(buf)

    r = auth.post(
        f"/api/data-sources?project_id={project}",
        files={
            "file": (
                "book.xlsx",
                buf.getvalue(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert r.status_code == 201
    assert r.json()["records"] == 2
    assert r.json()["type"] == "xlsx"


def test_upload_xlsx_multiple_tabs(auth, project):
    import io

    from openpyxl import Workbook

    wb = Workbook()
    ws1 = wb.active
    ws1.title = "Exhibitors"
    ws1.append(["exhibitor", "city"])
    ws1.append(["Acme", "Berlin"])
    ws1.append(["Globex", "Munich"])
    ws2 = wb.create_sheet("Booths")
    ws2.append(["booth", "hall"])
    ws2.append(["A12", "H1"])
    buf = io.BytesIO()
    wb.save(buf)

    r = auth.post(
        f"/api/data-sources?project_id={project}",
        files={
            "file": (
                "multi.xlsx",
                buf.getvalue(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert r.status_code == 201
    # records counts rows across every tab (2 exhibitors + 1 booth)
    assert r.json()["records"] == 3


def test_upload_unknown_project(auth):
    assert auth.post(
        "/api/data-sources?project_id=999999",
        files={"file": ("x.csv", CSV, "text/csv")},
    ).status_code == 404


def test_upload_bad_type(auth, project):
    assert auth.post(
        f"/api/data-sources?project_id={project}", files={"file": ("x.txt", "hi")}
    ).status_code == 400


def test_upload_empty(auth, project):
    assert auth.post(
        f"/api/data-sources?project_id={project}",
        files={"file": ("x.csv", "col1,col2\n")},
    ).status_code == 400


def test_list_and_get(auth, project):
    sid = auth.post(
        f"/api/data-sources?project_id={project}",
        files={"file": ("y.csv", CSV, "text/csv")},
    ).json()["id"]
    assert any(d["id"] == sid for d in auth.get("/api/data-sources").json())
    scoped = auth.get(f"/api/data-sources?project_id={project}").json()
    assert any(d["id"] == sid for d in scoped)
    assert auth.get(f"/api/data-sources/{sid}").json()["type"] == "csv"
    assert auth.get("/api/data-sources/999999").status_code == 404


def test_build_and_ontology_require_neo4j(auth, project):
    sid = auth.post(
        f"/api/data-sources?project_id={project}",
        files={"file": ("z.csv", CSV, "text/csv")},
    ).json()["id"]
    # neo4j is unreachable in the hermetic env
    assert auth.post(f"/api/data-sources/{sid}/build").status_code == 503
    assert auth.get(f"/api/ontology?project_id={project}").status_code == 503
    assert auth.post("/api/data-sources/999999/build").status_code == 404
