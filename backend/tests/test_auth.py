def test_me_requires_auth(client):
    assert client.get("/api/me").status_code == 401


def test_login_wrong_credentials(client):
    assert client.post(
        "/api/login", json={"username": "user", "password": "nope"}
    ).status_code == 401


def test_login_logout_flow(client):
    assert client.post(
        "/api/login", json={"username": "user", "password": "password"}
    ).status_code == 200
    assert client.get("/api/me").json() == {"username": "user"}
    assert client.post("/api/logout").json() == {"ok": True}
    assert client.get("/api/me").status_code == 401


def test_protected_routes_gated(client):
    assert client.get("/api/agents").status_code == 401
    assert client.get("/api/data-sources").status_code == 401


def test_me_clears_stale_cookie(client):
    # A stale/invalid cookie must be cleared on 401 to avoid a /login <-> / loop
    client.cookies.set("session", "stale-invalid-token")
    r = client.get("/api/me")
    assert r.status_code == 401
    assert "session=" in r.headers.get("set-cookie", "")
