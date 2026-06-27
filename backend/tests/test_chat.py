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


def test_chat_missing_agent(auth, monkeypatch):
    monkeypatch.setattr(chatmod, "get_provider", lambda *a, **k: _Fake())
    assert auth.post("/api/agents/999999/chat", json={"content": "x"}).status_code == 404


def test_chat_provider_error_returns_502(auth, monkeypatch):
    class Boom(LLMProvider):
        def complete(self, system, messages):
            raise RuntimeError("no key")

    monkeypatch.setattr(chatmod, "get_provider", lambda *a, **k: Boom())
    aid = _agent(auth)
    assert auth.post(f"/api/agents/{aid}/chat", json={"content": "x"}).status_code == 502
