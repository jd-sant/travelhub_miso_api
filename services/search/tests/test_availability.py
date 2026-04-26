from datetime import date

from domain.schemas.availability import PropertyAvailabilityQuery


def test_property_availability_endpoint_returns_available_for_seeded_property(client):
    response = client.get(
        "/api/v1/search/properties/11111111-1111-1111-1111-111111111111/availability",
        params={
            "check_in": "2026-04-10",
            "check_out": "2026-04-11",
            "guests": 2,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["property_id"] == "11111111-1111-1111-1111-111111111111"
    assert payload["available"] is True
    assert payload["price_from"] is not None


def test_property_availability_endpoint_returns_bad_request_for_invalid_window(client):
    response = client.get(
        "/api/v1/search/properties/11111111-1111-1111-1111-111111111111/availability",
        params={
            "check_in": "2026-04-12",
            "check_out": "2026-04-10",
            "guests": 2,
        },
    )

    assert response.status_code == 400


def test_property_availability_endpoint_rejects_invalid_uuid(client):
    response = client.get(
        "/api/v1/search/properties/not-a-uuid/availability",
        params={
            "check_in": "2026-04-10",
            "check_out": "2026-04-11",
            "guests": 2,
        },
    )

    assert response.status_code == 422


def test_property_availability_cache_hit_returns_same_payload(search_repository_with_cache):
    query = PropertyAvailabilityQuery(
        property_id="11111111-1111-1111-1111-111111111111",
        check_in=date(2026, 4, 10),
        check_out=date(2026, 4, 11),
        guests=2,
    )

    first = search_repository_with_cache.check_availability(query)
    second = search_repository_with_cache.check_availability(query)

    assert first.available is True
    assert second == first
