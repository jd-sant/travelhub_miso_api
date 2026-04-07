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

    def test_search_properties_success(self, client):
        response = client.get(
            "/api/v1/search",
            params={
                "ciudad": "Bogota",
                "check_in": "2026-04-10",
                "check_out": "2026-04-12",
                "huespedes": 2,
                "page": 1,
                "page_size": 10,
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["pagination"]["total"] >= 1
        assert payload["pagination"]["page"] == 1
        assert payload["pagination"]["page_size"] == 10
        assert len(payload["items"]) >= 1

    def test_search_properties_empty_state(self, client):
        response = client.get(
            "/api/v1/search",
            params={
                "ciudad": "Medellin",
                "check_in": "2026-04-10",
                "check_out": "2026-04-12",
                "huespedes": 2,
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["pagination"]["total"] == 0
        assert payload["items"] == []
        assert len(payload["empty_state"]) == 2

    def test_search_properties_missing_required(self, client):
        response = client.get(
            "/api/v1/search",
            params={
                "check_in": "2026-04-10",
                "check_out": "2026-04-12",
                "huespedes": 2,
            },
        )

        assert response.status_code == 422

    def test_search_properties_invalid_dates_rule(self, client):
        response = client.get(
            "/api/v1/search",
            params={
                "ciudad": "Bogota",
                "check_in": "2026-04-12",
                "check_out": "2026-04-10",
                "huespedes": 2,
            },
        )

        assert response.status_code == 400
        assert "check_out" in response.json()["detail"]

    def test_search_properties_invalid_price_range_rule(self, client):
        response = client.get(
            "/api/v1/search",
            params={
                "ciudad": "Bogota",
                "check_in": "2026-04-10",
                "check_out": "2026-04-12",
                "huespedes": 2,
                "precio_min": "200",
                "precio_max": "100",
            },
        )

        assert response.status_code == 400
        assert "precio_min" in response.json()["detail"]

    def test_search_properties_filters_by_amenities(self, client):
        response = client.get(
            "/api/v1/search",
            params={
                "ciudad": "Bogota",
                "check_in": "2026-04-10",
                "check_out": "2026-04-12",
                "huespedes": 2,
                "amenidades": ["wifi", "piscina"],
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["pagination"]["total"] >= 1
        for item in payload["items"]:
            assert "wifi" in item["amenidades"]
            assert "piscina" in item["amenidades"]

    def test_search_properties_filters_by_price_range(self, client):
        response = client.get(
            "/api/v1/search",
            params={
                "ciudad": "Bogota",
                "check_in": "2026-04-10",
                "check_out": "2026-04-12",
                "huespedes": 2,
                "precio_min": "90",
                "precio_max": "200",
            },
        )

        assert response.status_code == 200
        payload = response.json()
        for item in payload["items"]:
            assert float(item["precio_desde"]) >= 90
            assert float(item["precio_desde"]) <= 200

    def test_search_properties_invalid_page_limit(self, client):
        response = client.get(
            "/api/v1/search",
            params={
                "ciudad": "Bogota",
                "check_in": "2026-04-10",
                "check_out": "2026-04-12",
                "huespedes": 2,
                "page": 0,
            },
        )

        assert response.status_code == 422

    def test_search_properties_invalid_page_size_limit(self, client):
        response = client.get(
            "/api/v1/search",
            params={
                "ciudad": "Bogota",
                "check_in": "2026-04-10",
                "check_out": "2026-04-12",
                "huespedes": 2,
                "page_size": 101,
            },
        )

        assert response.status_code == 422
