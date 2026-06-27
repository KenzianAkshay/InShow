import app.chat as chatmod
from app.chat import extract_artifact
from app.llm import LLMProvider


def test_extract_artifact():
    txt = 'Done.\n```canvas\n{"type":"bar","data":[{"label":"A","value":1}]}\n```'
    clean, art = extract_artifact(txt)
    assert clean == "Done." and art["type"] == "bar"
    assert extract_artifact("plain") == ("plain", None)
    assert extract_artifact('```canvas\n{"type":"pie"}\n```')[1] is None  # bad type
    assert extract_artifact('```canvas\n{bad}\n```')[1] is None  # bad json


class _Fake(LLMProvider):
    def complete(self, system, messages):
        _Fake.system = system
        _Fake.messages = messages
        return 'Reply.\n```canvas\n{"type":"metrics","items":[{"label":"X","value":1}]}\n```'


def _agent(auth, **patch):
    pid = auth.post("/api/projects", json={"name": "P"}).json()["id"]
    aid = auth.post(
        "/api/agents", json={"name": "C", "show_project_id": pid}
    ).json()["id"]
    if patch:
        auth.patch(f"/api/agents/{aid}", json=patch)
    return aid


def test_chat_requires_auth(client):
    assert client.post("/api/agents/1/chat", json={"content": "hi"}).status_code == 401


def test_chat_roundtrip(auth, monkeypatch):
    captured = {}

    def fake_get(provider, model, api_key=None):
        captured["provider"] = provider
        captured["key"] = api_key
        return _Fake()

    monkeypatch.setattr(chatmod, "get_provider", fake_get)
    aid = _agent(auth, model_provider="claude", model_name="claude-opus-4-8",
                 config={"ontology_instructions": "booth logistics", "api_key": "sk-abc"})

    r = auth.post(f"/api/agents/{aid}/chat", json={"content": "Show metrics"}).json()
    assert r["content"] == "Reply."  # canvas block stripped
    assert r["artifact"]["type"] == "metrics"
    assert "traversal" in r

    # per-agent key + ontology instructions + canvas guide reached the provider
    assert captured["key"] == "sk-abc"
    assert "booth logistics" in _Fake.system
    assert "```canvas" in _Fake.system

    # second turn carries prior history
    auth.post(f"/api/agents/{aid}/chat", json={"content": "Thanks"})
    assert len(_Fake.messages) >= 3

    history = auth.get(f"/api/agents/{aid}/messages").json()
    assert [m["role"] for m in history] == ["user", "assistant", "user", "assistant"]
    assert history[1]["metadata"]["artifact"]["type"] == "metrics"


def test_chat_enforces_strict_grounding(auth, monkeypatch):
    monkeypatch.setattr(chatmod, "get_provider", lambda *a, **k: _Fake())
    aid = _agent(
        auth,
        model_provider="claude",
        model_name="claude-opus-4-8",
        config={"api_key": "sk-x"},
    )
    auth.post(
        f"/api/agents/{aid}/chat",
        json={"content": "What is the capital of France?"},
    )
    # The agent is told to use only the project's ontology/data, not the model's
    # own knowledge, and that this project has no data to answer from yet.
    assert "STRICT GROUNDING" in _Fake.system
    assert "outside or prior knowledge" in _Fake.system
    assert "no ingested data or ontology yet" in _Fake.system


def test_agents_delegate_without_key(auth_up):
    # No model key -> naming a sibling with a delegation verb routes to it.
    pid = auth_up.post("/api/projects", json={"name": "P"}).json()["id"]
    a = auth_up.post(
        "/api/agents",
        json={"name": "Booth Services", "type": "standard", "show_project_id": pid},
    ).json()["id"]
    auth_up.post(
        "/api/agents",
        json={"name": "Stats", "type": "standard", "show_project_id": pid},
    )
    r = auth_up.post(
        f"/api/agents/{a}/chat", json={"content": "ask Stats how many exhibitors"}
    )
    assert r.status_code == 200
    body = r.json()
    assert "Stats" in body["content"]
    assert "consulted" in body["content"].lower()


def test_ask_agent_tool_path(auth_up, monkeypatch):
    class Delegator(LLMProvider):
        def complete(self, system, messages):
            return "noop"

        def complete_with_tools(self, system, messages, tools, dispatch, max_rounds=6):
            if any(t["name"] == "ask_agent" for t in tools):
                out = dispatch("ask_agent", {"agent": "Stats", "question": "hi"})
                return f"Stats says: {out.get('answer') or out.get('error')}"
            return "leaf"

    monkeypatch.setattr(chatmod, "get_provider", lambda *a, **k: Delegator())
    pid = auth_up.post("/api/projects", json={"name": "P"}).json()["id"]
    a = auth_up.post(
        "/api/agents",
        json={"name": "Orchestrator", "type": "standard", "show_project_id": pid},
    ).json()["id"]
    auth_up.patch(f"/api/agents/{a}", json={"config": {"api_key": "sk-x"}})
    auth_up.post(
        "/api/agents",
        json={"name": "Stats", "type": "standard", "show_project_id": pid},
    )
    r = auth_up.post(f"/api/agents/{a}/chat", json={"content": "delegate please"})
    assert r.status_code == 200
    assert r.json()["content"].startswith("Stats says:")


def test_chat_missing_agent(auth, monkeypatch):
    monkeypatch.setattr(chatmod, "get_provider", lambda *a, **k: _Fake())
    assert auth.post("/api/agents/999999/chat", json={"content": "x"}).status_code == 404


def test_clear_messages(auth, monkeypatch):
    monkeypatch.setattr(chatmod, "get_provider", lambda *a, **k: _Fake())
    aid = _agent(auth, config={"api_key": "sk-x"})
    auth.post(f"/api/agents/{aid}/chat", json={"content": "hi"})
    assert len(auth.get(f"/api/agents/{aid}/messages").json()) == 2

    assert auth.delete(f"/api/agents/{aid}/messages").status_code == 204
    assert auth.get(f"/api/agents/{aid}/messages").json() == []

    assert auth.delete("/api/agents/999999/messages").status_code == 404


def test_clear_messages_requires_auth(client):
    assert client.delete("/api/agents/1/messages").status_code == 401


def test_chat_provider_error_returns_502(auth, monkeypatch):
    class Boom(LLMProvider):
        def complete(self, system, messages):
            raise RuntimeError("no key")

    monkeypatch.setattr(chatmod, "get_provider", lambda *a, **k: Boom())
    # With a key the provider is called; its failure (and no deterministic
    # fallback, since Neo4j is down) surfaces as 502.
    aid = _agent(auth, config={"api_key": "sk-x"})
    assert auth.post(f"/api/agents/{aid}/chat", json={"content": "x"}).status_code == 502


def test_chat_without_key_answers_deterministically(auth_up):
    # No API key configured -> the agent does not 502; it returns a deterministic
    # analytics answer (empty under the mock driver -> the guidance message).
    aid = _agent(auth_up)
    r = auth_up.post(f"/api/agents/{aid}/chat", json={"content": "chart it"})
    assert r.status_code == 200
    body = r.json()
    assert "deterministically" in body["content"]
    assert body["artifact"] is None
