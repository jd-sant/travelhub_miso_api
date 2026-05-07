"""End-to-end API contract tests using FastAPI's TestClient + fake services."""
from decimal import Decimal

from tests.conftest import make_property


class TestSearchHealthEndpoints:
    def test_health_check(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "healthy"}

    def test_search_status(self, client):
        response = client.get("/api/v1/search/status")
        assert response.status_code == 200
        assert response.json() == {"service": "search", "status": "ok"}


class TestSearchEndpoint:
    def test_search_returns_full_envelope(self, client, fake_properties):
        fake_properties.catalog = [
            make_property(name="P1", location="Bogota, Colombia", price_per_night=Decimal("100"))
        ]
        response = client.get(
            "/api/v1/search",
            params={
                "city": "Bogota",
                "check_in": "2026-04-10",
                "check_out": "2026-04-12",
                "guests": 2,
                "page": 1,
                "page_size": 10,
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert {"items", "pagination", "empty_state"} <= set(payload.keys())
        assert payload["pagination"] == {
            "total": 1,
            "page": 1,
            "page_size": 10,
            "total_pages": 1,
        }
        assert len(payload["items"]) == 1
        item = payload["items"][0]
        assert {
            "id",
            "name",
            "city",
            "country",
            "max_capacity",
            "main_image_url",
            "rating",
            "price_from",
            "currency",
            "amenities",
        } <= set(item.keys())
        assert item["city"] == "Bogota"
        assert item["country"] == "Colombia"

    def test_search_empty_state_when_no_results_returns_try_other_city(
        self, client, fake_properties
    ):
        fake_properties.catalog = []
        response = client.get(
            "/api/v1/search",
            params={
                "city": "Atlantis",
                "check_in": "2026-04-10",
                "check_out": "2026-04-12",
                "guests": 2,
            },
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["pagination"]["total"] == 0
        assert payload["items"] == []
        codes = [s["code"] for s in payload["empty_state"]]
        assert "TRY_OTHER_CITY" in codes

    def test_search_empty_state_when_dates_block_returns_try_other_dates(
        self, client, fake_properties, fake_reservations
    ):
        # Properties exist but all are blocked → suggest other dates
        p = make_property(location="Bogota, Colombia")
        fake_properties.catalog = [p]
        fake_reservations.blocked_ids = {p.id}

        response = client.get(
            "/api/v1/search",
            params={
                "city": "Bogota",
                "check_in": "2026-04-10",
                "check_out": "2026-04-12",
                "guests": 2,
            },
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["items"] == []
        codes = [s["code"] for s in payload["empty_state"]]
        assert "TRY_OTHER_DATES" in codes

    def test_missing_required_returns_422(self, client):
        response = client.get(
            "/api/v1/search",
            params={
                "check_in": "2026-04-10",
                "check_out": "2026-04-12",
                "guests": 2,
            },
        )
        assert response.status_code == 422

    def test_invalid_dates_rule_returns_400(self, client):
        response = client.get(
            "/api/v1/search",
            params={
                "city": "Bogota",
                "check_in": "2026-04-12",
                "check_out": "2026-04-10",
                "guests": 2,
            },
        )
        assert response.status_code == 400
        assert "check_out" in response.json()["detail"]

    def test_invalid_price_range_rule_returns_400(self, client):
        response = client.get(
            "/api/v1/search",
            params={
                "city": "Bogota",
                "check_in": "2026-04-10",
                "check_out": "2026-04-12",
                "guests": 2,
                "min_price": "200",
                "max_price": "100",
            },
        )
        assert response.status_code == 400
        assert "min_price" in response.json()["detail"]

    def test_invalid_page_returns_422(self, client):
        response = client.get(
            "/api/v1/search",
            params={
                "city": "Bogota",
                "check_in": "2026-04-10",
                "check_out": "2026-04-12",
                "guests": 2,
                "page": 0,
            },
        )
        assert response.status_code == 422

    def test_invalid_page_size_returns_422(self, client):
        response = client.get(
            "/api/v1/search",
            params={
                "city": "Bogota",
                "check_in": "2026-04-10",
                "check_out": "2026-04-12",
                "guests": 2,
                "page_size": 101,
            },
        )
        assert response.status_code == 422

    def test_filters_by_amenities(self, client, fake_properties):
        a = make_property(
            name="With wifi & pool",
            location="Bogota, Colombia",
            amenities=["WiFi Fibra de Alta Velocidad", "Piscina Infinita Privada"],
        )
        b = make_property(
            name="Without wifi",
            location="Bogota, Colombia",
            amenities=["Spa"],
        )
        fake_properties.catalog = [a, b]

        response = client.get(
            "/api/v1/search",
            params={
                "city": "Bogota",
                "check_in": "2026-04-10",
                "check_out": "2026-04-12",
                "guests": 2,
                "amenities": ["wifi", "piscina"],
            },
        )
        assert response.status_code == 200
        payload = response.json()
        ids = {item["id"] for item in payload["items"]}
        assert ids == {str(a.id)}

    def test_filters_by_price_range(self, client, fake_properties):
        cheap = make_property(name="cheap", price_per_night=Decimal("50"))
        mid = make_property(name="mid", price_per_night=Decimal("150"))
        expensive = make_property(name="expensive", price_per_night=Decimal("500"))
        fake_properties.catalog = [cheap, mid, expensive]

        response = client.get(
            "/api/v1/search",
            params={
                "city": "Bogota",
                "check_in": "2026-04-10",
                "check_out": "2026-04-12",
                "guests": 2,
                "min_price": "90",
                "max_price": "200",
            },
        )
        assert response.status_code == 200
        payload = response.json()
        for item in payload["items"]:
            assert 90 <= float(item["price_from"]) <= 200

    def test_returns_503_when_properties_unavailable(self, client, fake_properties):
        from errors import PropertiesServiceUnavailableError

        fake_properties.raises = PropertiesServiceUnavailableError("down")
        response = client.get(
            "/api/v1/search",
            params={
                "city": "Bogota",
                "check_in": "2026-04-10",
                "check_out": "2026-04-12",
                "guests": 2,
            },
        )
        assert response.status_code == 503

    def test_returns_503_when_reservations_unavailable(
        self, client, fake_properties, fake_reservations
    ):
        from errors import ReservationsServiceUnavailableError

        fake_properties.catalog = [make_property(location="Bogota, Colombia")]
        fake_reservations.raises = ReservationsServiceUnavailableError("down")
        response = client.get(
            "/api/v1/search",
            params={
                "city": "Bogota",
                "check_in": "2026-04-10",
                "check_out": "2026-04-12",
                "guests": 2,
            },
        )
        assert response.status_code == 503
