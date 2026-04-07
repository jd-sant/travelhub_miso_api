class TestSearchHealthEndpoints:
    def test_health_check(self, client):
        response = client.get("/health")

        assert response.status_code == 200
        assert response.json() == {"status": "healthy"}

    def test_search_status(self, client):
        response = client.get("/api/v1/search/status")

        assert response.status_code == 200
        assert response.json() == {"service": "search", "status": "ok"}
