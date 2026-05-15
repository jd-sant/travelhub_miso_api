from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from db.session import engine
from entrypoints.api.main import app


def test_health_ok():
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_503_when_db_unavailable(monkeypatch):
    def boom(*_args, **_kwargs):
        raise SQLAlchemyError("simulated db outage")

    monkeypatch.setattr(engine, "connect", boom)
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 503
    assert response.json()["detail"] == "database unavailable"
