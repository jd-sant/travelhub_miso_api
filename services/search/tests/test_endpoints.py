class TestSearchHealthEndpoints:
    def test_health_check(self, client):
        response = client.get("/health")

        assert response.status_code == 200
        assert response.json() == {"status": "healthy"}

    def test_search_status(self, client):
        response = client.get("/api/v1/search/status")

        assert response.status_code == 200
        assert response.json() == {"service": "search", "status": "ok"}

    def test_list_test_dataset(self, client):
        response = client.get("/api/v1/search/test-dataset")

        assert response.status_code == 200
        payload = response.json()
        assert payload["counts"]["propiedades"] >= 1
        assert payload["counts"]["tipos_habitacion"] >= 1
        assert payload["counts"]["planes_tarifa"] >= 1
        assert payload["counts"]["amenidades"] >= 1
        assert payload["counts"]["servicios"] >= 1
        assert len(payload["propiedades"]) >= 1
