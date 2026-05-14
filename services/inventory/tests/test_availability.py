from uuid import UUID, uuid4

from assembly import get_property_availability_use_case
from conftest import FakeAvailabilityUseCase
from entrypoints.api.main import app


SEEDED_ID = UUID("11111111-1111-1111-1111-111111111111")


def test_availability_endpoint_returns_available(client):
    app.dependency_overrides[get_property_availability_use_case] = lambda: FakeAvailabilityUseCase()
    try:
        response = client.get(
            f"/api/v1/inventory/properties/{SEEDED_ID}/availability",
            params={"check_in": "2026-04-10", "check_out": "2026-04-11", "guests": 2},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["property_id"] == str(SEEDED_ID)
        assert payload["available"] is True
        assert payload["price_from"] == 180000.0
        assert payload["currency"] == "COP"
    finally:
        app.dependency_overrides.clear()


def test_availability_endpoint_returns_unavailable(client):
    app.dependency_overrides[get_property_availability_use_case] = lambda: FakeAvailabilityUseCase()
    try:
        response = client.get(
            f"/api/v1/inventory/properties/{SEEDED_ID}/availability",
            params={"check_in": "2026-04-12", "check_out": "2026-04-13", "guests": 2},
        )
        assert response.status_code == 200
        assert response.json()["available"] is False
    finally:
        app.dependency_overrides.clear()


def test_availability_endpoint_returns_400_for_invalid_window(client):
    response = client.get(
        f"/api/v1/inventory/properties/{SEEDED_ID}/availability",
        params={"check_in": "2026-04-12", "check_out": "2026-04-10", "guests": 2},
    )
    assert response.status_code == 400


def test_availability_endpoint_returns_422_for_invalid_uuid(client):
    response = client.get(
        "/api/v1/inventory/properties/not-a-uuid/availability",
        params={"check_in": "2026-04-10", "check_out": "2026-04-11", "guests": 2},
    )
    assert response.status_code == 422
