import os
import tempfile

# Configure a hermetic environment BEFORE importing the app.
_tmp = tempfile.mkdtemp(prefix="inshow_test_")
os.environ["DATABASE_PATH"] = os.path.join(_tmp, "test.db")
os.environ["DATA_DIR"] = os.path.join(_tmp, "uploads")
os.environ["NEO4J_URI"] = "bolt://127.0.0.1:1"  # refused fast -> neo4j "down"
os.environ.pop("ANTHROPIC_API_KEY", None)
os.environ.pop("OPENAI_API_KEY", None)

import pytest
from fastapi.testclient import TestClient

from app.main import app


class _MockSession:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def run(self, *a, **k):
        return []


class MockDriver:
    """Stands in for a healthy Neo4j driver."""

    def verify_connectivity(self):
        return True

    def session(self):
        return _MockSession()

    def close(self):
        pass


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def auth(client):
    r = client.post("/api/login", json={"username": "user", "password": "password"})
    assert r.status_code == 200
    return client


@pytest.fixture()
def auth_up(auth):
    auth.app.state.neo4j = MockDriver()
    return auth


@pytest.fixture()
def project(auth):
    """A Show Project that agents and data sources belong to."""
    r = auth.post("/api/projects", json={"name": "CES 2026"})
    assert r.status_code == 201
    return r.json()["id"]
