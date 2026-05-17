"""Tests for GET /api/v1/properties/search endpoint."""
from uuid import uuid4

from fastapi.testclient import TestClient

from db.seed import (
    ALPINE_LODGE_ID,
    ANDINO_APARTHOTEL_ID,
    BEACHFRONT_PENTHOUSE_ID,
    CANDELARIA_HOSTEL_ID,
    CIKOS_EXECUTIVE_SUITES_ID,
    RENAISSANCE_ESTATE_ID,
    TROPICAL_VILLA_ID,
)


def test_search_returns_paginated_envelope(client: TestClient):
    response = client.get("/api/v1/properties/search")
    assert response.status_code == 200
    data = response.json()

    assert "items" in data
    assert "pagination" in data
    assert {"total", "page", "page_size", "total_pages"} <= set(data["pagination"].keys())
    assert isinstance(data["items"], list)


def test_search_default_returns_all_active_seeded(client: TestClient):
    response = client.get("/api/v1/properties/search")
    assert response.status_code == 200
    data = response.json()
    # 7 seeded, all active
    assert data["pagination"]["total"] == 7
    assert len(data["items"]) == 7


def test_search_filter_by_city_partial_case_insensitive(client: TestClient):
    response = client.get("/api/v1/properties/search?city=bogot")
    assert response.status_code == 200
    data = response.json()
    # 3 properties seeded in Bogotá
    assert data["pagination"]["total"] == 3
    ids = {item["id"] for item in data["items"]}
    assert ids == {
        str(CIKOS_EXECUTIVE_SUITES_ID),
        str(CANDELARIA_HOSTEL_ID),
        str(ANDINO_APARTHOTEL_ID),
    }


def test_search_filter_by_city_no_match(client: TestClient):
    response = client.get("/api/v1/properties/search?city=Atlantis")
    assert response.status_code == 200
    data = response.json()
    assert data["pagination"]["total"] == 0
    assert data["items"] == []


def test_search_filter_by_min_price(client: TestClient):
    response = client.get("/api/v1/properties/search?min_price=2000")
    assert response.status_code == 200
    data = response.json()
    ids = {item["id"] for item in data["items"]}
    assert str(BEACHFRONT_PENTHOUSE_ID) in ids
    assert str(CIKOS_EXECUTIVE_SUITES_ID) in ids
    assert str(ALPINE_LODGE_ID) not in ids


def test_search_filter_by_max_price(client: TestClient):
    response = client.get("/api/v1/properties/search?max_price=1000")
    assert response.status_code == 200
    data = response.json()
    ids = {item["id"] for item in data["items"]}
    assert str(ALPINE_LODGE_ID) in ids
    assert str(BEACHFRONT_PENTHOUSE_ID) not in ids


def test_search_filter_by_price_range(client: TestClient):
    response = client.get("/api/v1/properties/search?min_price=1200&max_price=1700")
    assert response.status_code == 200
    data = response.json()
    ids = {item["id"] for item in data["items"]}
    assert str(RENAISSANCE_ESTATE_ID) in ids
    assert str(TROPICAL_VILLA_ID) in ids
    assert str(ALPINE_LODGE_ID) not in ids
    assert str(BEACHFRONT_PENTHOUSE_ID) not in ids


def test_search_filter_by_min_guests(client: TestClient):
    response = client.get("/api/v1/properties/search?min_guests=12")
    assert response.status_code == 200
    data = response.json()
    ids = {item["id"] for item in data["items"]}
    # max_guests >= 12 → Renaissance(12), Alpine(14), Cikos(24)
    assert ids == {
        str(RENAISSANCE_ESTATE_ID),
        str(ALPINE_LODGE_ID),
        str(CIKOS_EXECUTIVE_SUITES_ID),
    }


def test_search_filter_by_amenity_wifi(client: TestClient):
    response = client.get("/api/v1/properties/search?amenities=wifi")
    assert response.status_code == 200
    data = response.json()
    ids = {item["id"] for item in data["items"]}
    # Only Renaissance and Cikos mention WiFi by name
    assert str(RENAISSANCE_ESTATE_ID) in ids
    assert str(CIKOS_EXECUTIVE_SUITES_ID) in ids


def test_search_filter_by_amenity_piscina(client: TestClient):
    response = client.get("/api/v1/properties/search?amenities=piscina")
    assert response.status_code == 200
    data = response.json()
    ids = {item["id"] for item in data["items"]}
    assert str(RENAISSANCE_ESTATE_ID) in ids  # "Piscina Infinita Privada"
    assert str(TROPICAL_VILLA_ID) in ids  # "Piscina Infinita"


def test_search_filter_by_multiple_amenities_anded(client: TestClient):
    # piscina AND wifi → only Renaissance has both
    response = client.get("/api/v1/properties/search?amenities=piscina&amenities=wifi")
    assert response.status_code == 200
    data = response.json()
    ids = {item["id"] for item in data["items"]}
    assert ids == {str(RENAISSANCE_ESTATE_ID)}


def test_search_filter_by_ids(client: TestClient):
    response = client.get(
        f"/api/v1/properties/search?ids={RENAISSANCE_ESTATE_ID}&ids={ALPINE_LODGE_ID}"
    )
    assert response.status_code == 200
    data = response.json()
    ids = {item["id"] for item in data["items"]}
    assert ids == {str(RENAISSANCE_ESTATE_ID), str(ALPINE_LODGE_ID)}


def test_search_filter_by_unknown_id_returns_empty(client: TestClient):
    response = client.get(f"/api/v1/properties/search?ids={uuid4()}")
    assert response.status_code == 200
    data = response.json()
    assert data["pagination"]["total"] == 0


def test_search_pagination(client: TestClient):
    page1 = client.get("/api/v1/properties/search?page=1&page_size=2").json()
    page2 = client.get("/api/v1/properties/search?page=2&page_size=2").json()
    page3 = client.get("/api/v1/properties/search?page=3&page_size=2").json()
    page4 = client.get("/api/v1/properties/search?page=4&page_size=2").json()

    assert page1["pagination"]["total"] == 7
    assert page1["pagination"]["page"] == 1
    assert page1["pagination"]["page_size"] == 2
    assert page1["pagination"]["total_pages"] == 4
    assert len(page1["items"]) == 2
    assert len(page2["items"]) == 2
    assert len(page3["items"]) == 2
    assert len(page4["items"]) == 1

    ids1 = {i["id"] for i in page1["items"]}
    ids2 = {i["id"] for i in page2["items"]}
    ids3 = {i["id"] for i in page3["items"]}
    ids4 = {i["id"] for i in page4["items"]}
    assert ids1.isdisjoint(ids2)
    assert ids1.isdisjoint(ids3)
    assert ids1.isdisjoint(ids4)
    assert ids2.isdisjoint(ids3)
    assert ids2.isdisjoint(ids4)
    assert ids3.isdisjoint(ids4)


def test_search_sort_by_price_asc(client: TestClient):
    response = client.get("/api/v1/properties/search?sort_by=price&sort_dir=asc")
    data = response.json()
    prices = [item["price_per_night"] for item in data["items"]]
    assert prices == sorted(prices)


def test_search_sort_by_price_desc(client: TestClient):
    response = client.get("/api/v1/properties/search?sort_by=price&sort_dir=desc")
    data = response.json()
    prices = [item["price_per_night"] for item in data["items"]]
    assert prices == sorted(prices, reverse=True)


def test_search_sort_by_rating_desc(client: TestClient):
    response = client.get("/api/v1/properties/search?sort_by=rating&sort_dir=desc")
    data = response.json()
    ratings = [item["rating"] for item in data["items"]]
    assert ratings == sorted(ratings, reverse=True)


def test_search_sort_by_name_asc(client: TestClient):
    response = client.get("/api/v1/properties/search?sort_by=name&sort_dir=asc")
    data = response.json()
    names = [item["name"] for item in data["items"]]
    assert names == sorted(names)


def test_search_city_filter_combined_with_price_asc(client: TestClient):
    response = client.get(
        "/api/v1/properties/search?city=Bogot&sort_by=price&sort_dir=asc"
    )
    data = response.json()
    ids = [item["id"] for item in data["items"]]
    # Bogotá properties ordered by ascending price:
    # Hostal (95k) → Cikos (180k) → Aparthotel (320k)
    assert ids == [
        str(CANDELARIA_HOSTEL_ID),
        str(CIKOS_EXECUTIVE_SUITES_ID),
        str(ANDINO_APARTHOTEL_ID),
    ]


def test_search_city_filter_combined_with_price_desc(client: TestClient):
    response = client.get(
        "/api/v1/properties/search?city=Bogot&sort_by=price&sort_dir=desc"
    )
    data = response.json()
    ids = [item["id"] for item in data["items"]]
    assert ids == [
        str(ANDINO_APARTHOTEL_ID),
        str(CIKOS_EXECUTIVE_SUITES_ID),
        str(CANDELARIA_HOSTEL_ID),
    ]


def test_search_city_filter_combined_with_rating_desc(client: TestClient):
    response = client.get(
        "/api/v1/properties/search?city=Bogot&sort_by=rating&sort_dir=desc"
    )
    data = response.json()
    ids = [item["id"] for item in data["items"]]
    # Aparthotel (4.95) → Cikos (4.84) → Hostal (4.55)
    assert ids == [
        str(ANDINO_APARTHOTEL_ID),
        str(CIKOS_EXECUTIVE_SUITES_ID),
        str(CANDELARIA_HOSTEL_ID),
    ]


def test_search_city_filter_combined_with_name_asc(client: TestClient):
    response = client.get(
        "/api/v1/properties/search?city=Bogot&sort_by=name&sort_dir=asc"
    )
    data = response.json()
    names = [item["name"] for item in data["items"]]
    assert names == [
        "Aparthotel Andino Premium",
        "Hostal Boutique La Candelaria",
        "Hotel Cikos Executive Suites",
    ]


def test_search_invalid_page_returns_422(client: TestClient):
    response = client.get("/api/v1/properties/search?page=0")
    assert response.status_code == 422


def test_search_invalid_page_size_returns_422(client: TestClient):
    response = client.get("/api/v1/properties/search?page_size=200")
    assert response.status_code == 422


def test_search_includes_paginated_metadata(client: TestClient):
    response = client.get("/api/v1/properties/search?page=2&page_size=2")
    data = response.json()
    assert data["pagination"] == {
        "total": 7,
        "page": 2,
        "page_size": 2,
        "total_pages": 4,
    }


def test_search_combined_filters(client: TestClient):
    # Bogotá + min_guests=10 → Cikos (24 guests)
    response = client.get(
        "/api/v1/properties/search?city=Bogot&min_guests=10&min_price=100000"
    )
    data = response.json()
    ids = {item["id"] for item in data["items"]}
    assert ids == {str(CIKOS_EXECUTIVE_SUITES_ID)}


def test_search_route_does_not_collide_with_detail_uuid(client: TestClient):
    # /search must not be interpreted as a UUID for /{property_id}
    response = client.get("/api/v1/properties/search")
    assert response.status_code == 200
    assert "items" in response.json()
