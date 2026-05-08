"""Tests for the per-property /availability endpoint and use case."""
from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

from domain.schemas.availability import PropertyAvailabilityQuery
from domain.use_cases.check_property_availability import (
    CheckPropertyAvailabilityUseCase,
)
from conftest import make_property


SEEDED_ID = UUID("11111111-1111-1111-1111-111111111111")


def test_availability_endpoint_returns_available_when_property_active_and_not_blocked(
    client, fake_properties
):
    fake_properties.catalog = [
        make_property(
            id=SEEDED_ID, location="Bogota, Colombia", price_per_night=Decimal("100")
        )
    ]
    response = client.get(
        f"/api/v1/search/properties/{SEEDED_ID}/availability",
        params={
            "check_in": "2026-04-10",
            "check_out": "2026-04-11",
            "guests": 2,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["property_id"] == str(SEEDED_ID)
    assert payload["available"] is True
    assert payload["price_from"] == 100.0
    assert payload["currency"] == "COP"


def test_availability_endpoint_returns_unavailable_when_blocked(
    client, fake_properties, fake_reservations
):
    fake_properties.catalog = [make_property(id=SEEDED_ID, location="Bogota, Colombia")]
    fake_reservations.blocked_ids = {SEEDED_ID}

    response = client.get(
        f"/api/v1/search/properties/{SEEDED_ID}/availability",
        params={
            "check_in": "2026-04-10",
            "check_out": "2026-04-11",
            "guests": 2,
        },
    )
    assert response.status_code == 200
    assert response.json()["available"] is False


def test_availability_endpoint_returns_unavailable_when_property_unknown(
    client, fake_properties
):
    fake_properties.catalog = []
    response = client.get(
        f"/api/v1/search/properties/{uuid4()}/availability",
        params={
            "check_in": "2026-04-10",
            "check_out": "2026-04-11",
            "guests": 2,
        },
    )
    assert response.status_code == 200
    assert response.json()["available"] is False


def test_availability_endpoint_returns_400_for_invalid_window(client):
    response = client.get(
        f"/api/v1/search/properties/{SEEDED_ID}/availability",
        params={
            "check_in": "2026-04-12",
            "check_out": "2026-04-10",
            "guests": 2,
        },
    )
    assert response.status_code == 400


def test_availability_endpoint_returns_422_for_invalid_uuid(client):
    response = client.get(
        "/api/v1/search/properties/not-a-uuid/availability",
        params={
            "check_in": "2026-04-10",
            "check_out": "2026-04-11",
            "guests": 2,
        },
    )
    assert response.status_code == 422


def test_use_case_inactive_property_returns_unavailable(
    fake_properties, fake_reservations
):
    p = make_property(id=SEEDED_ID, status=0)
    fake_properties.catalog = [p]
    use_case = CheckPropertyAvailabilityUseCase(fake_properties, fake_reservations)

    result = use_case.execute(
        PropertyAvailabilityQuery(
            property_id=SEEDED_ID,
            check_in=date(2026, 4, 10),
            check_out=date(2026, 4, 11),
            guests=2,
        )
    )
    assert result.available is False
    assert result.price_from is None


def test_use_case_capacity_exceeded_returns_unavailable(
    fake_properties, fake_reservations
):
    p = make_property(id=SEEDED_ID, max_guests=2)
    fake_properties.catalog = [p]
    use_case = CheckPropertyAvailabilityUseCase(fake_properties, fake_reservations)

    result = use_case.execute(
        PropertyAvailabilityQuery(
            property_id=SEEDED_ID,
            check_in=date(2026, 4, 10),
            check_out=date(2026, 4, 11),
            guests=10,
        )
    )
    assert result.available is False
