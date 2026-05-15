from contextlib import contextmanager

from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from db.session import engine
from entrypoints.api.main import create_application


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
