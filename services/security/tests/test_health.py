import os
from contextlib import contextmanager

os.environ.setdefault("ENV", "test")
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")

from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from db.session import engine
from entrypoints.api.main import app, create_application


class _FakeConn:
    def execute(self, *_args, **_kwargs):
        return None


@contextmanager
def _fake_connect_ok():
    yield _FakeConn()


def test_health_ok(monkeypatch):
    monkeypatch.setattr(engine, "connect", _fake_connect_ok)
    client = TestClient(create_application())
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_health_503_when_db_unavailable(monkeypatch):
    def boom(*_args, **_kwargs):
        raise SQLAlchemyError("simulated db outage")

    monkeypatch.setattr(engine, "connect", boom)
    client = TestClient(create_application())
    response = client.get("/health")
    assert response.status_code == 503
    assert response.json()["detail"] == "database unavailable"


client = TestClient(app)


class TestHealthEndpoints:
    def test_liveness(self):
        resp = client.get("/healthz/liveness")
        assert resp.status_code == 200
        assert resp.json() == {"status": "alive"}

    def test_readiness(self):
        resp = client.get("/healthz/readiness")
        assert resp.status_code in (200, 503)
        if resp.status_code == 200:
            assert resp.json()["status"] == "ready"
