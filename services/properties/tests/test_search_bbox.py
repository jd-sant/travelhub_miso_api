from fastapi.testclient import TestClient


# Bounding boxes around the seeded canonical demo properties:
# - Renaissance Estate (Florencia, Italy):    lat 43.8047, lng 11.2844
# - Bogotá Cikos / Candelaria / Andino:       lat ~4.59-4.67, lng ~-74.07
RENAISSANCE_BBOX = {
    "min_lat": 43.70,
    "max_lat": 43.90,
    "min_lng": 11.20,
    "max_lng": 11.40,
}

BOGOTA_BBOX = {
    "min_lat": 4.50,
    "max_lat": 4.78,
    "min_lng": -74.12,
    "max_lng": -74.02,
}


def test_bbox_filters_to_geographic_zone(client: TestClient):
    response = client.get("/api/v1/properties/search", params=BOGOTA_BBOX)
    assert response.status_code == 200
    data = response.json()
    assert data["pagination"]["total"] >= 1
    for item in data["items"]:
        assert item["latitude"] is not None
        assert BOGOTA_BBOX["min_lat"] <= item["latitude"] <= BOGOTA_BBOX["max_lat"]
        assert BOGOTA_BBOX["min_lng"] <= item["longitude"] <= BOGOTA_BBOX["max_lng"]


def test_bbox_excludes_outside_properties(client: TestClient):
    response = client.get("/api/v1/properties/search", params=BOGOTA_BBOX)
    data = response.json()
    names = {it["name"] for it in data["items"]}
    # Renaissance is in Florence — must not appear in a Bogotá bbox.
    assert "Mansión Renacentista & Viñedo Privado" not in names


def test_bbox_combined_with_city_filter(client: TestClient):
    """City and bbox must compose as AND. A Florence bbox + city=bogot returns nothing."""
    response = client.get(
        "/api/v1/properties/search",
        params={**RENAISSANCE_BBOX, "city": "bogot"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["pagination"]["total"] == 0


def test_bbox_alone_around_renaissance_returns_renaissance(client: TestClient):
    response = client.get("/api/v1/properties/search", params=RENAISSANCE_BBOX)
    assert response.status_code == 200
    names = {it["name"] for it in response.json()["items"]}
    assert "Mansión Renacentista & Viñedo Privado" in names


def test_lat_lng_present_in_search_response(client: TestClient):
    response = client.get("/api/v1/properties/search")
    assert response.status_code == 200
    items = response.json()["items"]
    # All seeded canonical properties have coordinates populated.
    assert all("latitude" in it and "longitude" in it for it in items)
    assert any(it["latitude"] is not None for it in items)


def test_out_of_range_lat_returns_422(client: TestClient):
    response = client.get(
        "/api/v1/properties/search",
        params={"min_lat": -91.0, "max_lat": 0.0, "min_lng": 0.0, "max_lng": 1.0},
    )
    assert response.status_code == 422
