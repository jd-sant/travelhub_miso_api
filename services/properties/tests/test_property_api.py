"""API endpoint tests for properties service"""
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlmodel import Session

from db.seed import RENAISSANCE_ESTATE_ID, BEACHFRONT_PENTHOUSE_ID


def test_list_properties_endpoint_success(client: TestClient):
    """Test GET /api/v1/properties endpoint to list all properties"""
    response = client.get("/api/v1/properties")

    assert response.status_code == 200
    data = response.json()
    
    # Should have 4 seeded properties
    assert len(data) == 4
    
    # Check basic structure
    for prop in data:
        assert "id" in prop
        assert "name" in prop
        assert "description" in prop
        assert "location" in prop
        assert "price_per_night" in prop
        assert "images" in prop
        assert isinstance(prop["images"], list)


def test_list_properties_endpoint_empty_filter(client: TestClient):
    """Test GET /api/v1/properties endpoint returns data"""
    response = client.get("/api/v1/properties")

    assert response.status_code == 200
    data = response.json()
    assert len(data) > 0


def test_get_property_endpoint_with_seeded_data(client: TestClient):
    """Test GET /api/v1/properties/{id} endpoint with seeded data"""
    # Use one of the seeded property IDs
    response = client.get(f"/api/v1/properties/{RENAISSANCE_ESTATE_ID}")

    assert response.status_code == 200
    data = response.json()
    
    assert data["id"] == str(RENAISSANCE_ESTATE_ID)
    assert data["name"] == "Mansión Renacentista & Viñedo Privado"
    assert data["location"] == "Fiesole, Florencia"
    assert data["price_per_night"] == 1240.0
    assert data["rating"] == 4.98
    assert data["bedrooms"] == 4
    assert data["bathrooms"] == 4.5
    assert data["max_guests"] == 12
    assert data["status"] == 1
    
    # Should have images
    assert len(data["images"]) == 5
    assert data["images"][0]["url"] == "https://images.unsplash.com/photo-1564013799919-ab600027ffc6?w=800&q=80"
    
    # Should have reviews
    assert len(data["reviews"]) == 2


def test_get_property_endpoint_not_found(client: TestClient):
    """Test GET /api/v1/properties/{id} endpoint when not found"""
    non_existent_id = uuid4()

    response = client.get(f"/api/v1/properties/{non_existent_id}")

    assert response.status_code == 404
    data = response.json()
    assert "detail" in data


def test_get_property_endpoint_multiple_properties(client: TestClient):
    """Test that we can get multiple different seeded properties"""
    # Get first property
    response1 = client.get(f"/api/v1/properties/{RENAISSANCE_ESTATE_ID}")
    assert response1.status_code == 200
    data1 = response1.json()
    
    # Get second property
    response2 = client.get(f"/api/v1/properties/{BEACHFRONT_PENTHOUSE_ID}")
    assert response2.status_code == 200
    data2 = response2.json()
    
    # They should be different properties
    assert data1["id"] != data2["id"]
    assert data1["name"] != data2["name"]
    assert data1["location"] != data2["location"]


def test_health_check(client: TestClient):
    """Test health check endpoint"""
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}
