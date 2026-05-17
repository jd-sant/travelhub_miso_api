import os

os.environ["ENV"] = "test"
os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = "sqlite:///./test.db"

from fastapi.testclient import TestClient
from entrypoints.api.main import app

client = TestClient(app)


class TestHealthEndpoints:
    def test_legacy_health(self):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

    def test_liveness(self):
        resp = client.get("/healthz/liveness")
        assert resp.status_code == 200
        assert resp.json() == {"status": "alive"}

    def test_readiness(self):
        resp = client.get("/healthz/readiness")
        assert resp.status_code in (200, 503)
        if resp.status_code == 200:
            assert resp.json()["status"] == "ready"
