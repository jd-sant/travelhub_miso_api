"""Tests for seeded data and endpoints"""
import uuid

from fastapi.testclient import TestClient
from sqlmodel import Session

from db.seed import RENAISSANCE_ESTATE_ID, BEACHFRONT_PENTHOUSE_ID, ALPINE_LODGE_ID, TROPICAL_VILLA_ID


def test_list_properties_returns_seeded_data(
    client: TestClient, session: Session
):
    """Test that list_properties returns all 4 seeded properties"""
    response = client.get("/api/v1/properties")

    assert response.status_code == 200
    data = response.json()
    
    # Should have exactly 4 seeded properties
    assert len(data) == 4
    
    # Check property names
    names = {prop["name"] for prop in data}
    expected_names = {
        "Mansión Renacentista & Viñedo Privado",
        "Penthouse Moderno Frente a la Playa",
        "Refugio Alpino de Montaña",
        "Villa Paraíso Tropical",
    }
    assert names == expected_names


def test_get_renaissance_estate(client: TestClient):
    """Test getting Renaissance Estate by ID"""
    response = client.get(f"/api/v1/properties/{RENAISSANCE_ESTATE_ID}")

    assert response.status_code == 200
    data = response.json()
    
    assert data["id"] == str(RENAISSANCE_ESTATE_ID)
    assert data["name"] == "Mansión Renacentista & Viñedo Privado"
    assert data["location"] == "Fiesole, Florence"
    assert data["bedrooms"] == 4
    assert data["bathrooms"] == 4.5
    assert data["max_guests"] == 12
    assert data["price_per_night"] == 1240.0
    assert data["currency"] == "COP"
    assert data["rating"] == 4.98
    assert data["review_count"] == 54
    
    # Check images (should have 5)
    assert len(data["images"]) == 5
    assert data["images"][0]["position"] == 0
    assert data["images"][0]["url"] == "/mock/property-1.svg"
    
    # Check reviews (should have 2)
    assert len(data["reviews"]) == 2
    assert data["reviews"][0]["author"] == "Sarah Holkins"
    assert data["reviews"][0]["rating"] == 5


def test_get_beachfront_penthouse(client: TestClient):
    """Test getting Modern Beachfront Penthouse by ID"""
    response = client.get(f"/api/v1/properties/{BEACHFRONT_PENTHOUSE_ID}")

    assert response.status_code == 200
    data = response.json()
    
    assert data["id"] == str(BEACHFRONT_PENTHOUSE_ID)
    assert data["name"] == "Penthouse Moderno Frente a la Playa"
    assert data["location"] == "Miami Beach, Florida"
    assert data["bedrooms"] == 3
    assert data["bathrooms"] == 3.0
    assert data["max_guests"] == 8
    assert data["price_per_night"] == 2150.0
    assert data["currency"] == "USD"
    assert data["rating"] == 4.87
    assert len(data["images"]) == 5
    assert len(data["reviews"]) == 2


def test_get_alpine_lodge(client: TestClient):
    """Test getting Alpine Mountain Lodge by ID"""
    response = client.get(f"/api/v1/properties/{ALPINE_LODGE_ID}")

    assert response.status_code == 200
    data = response.json()
    
    assert data["id"] == str(ALPINE_LODGE_ID)
    assert data["name"] == "Refugio Alpino de Montaña"
    assert data["location"] == "Chamonix, French Alps"
    assert data["bedrooms"] == 5
    assert data["bathrooms"] == 4.0
    assert data["max_guests"] == 14
    assert data["price_per_night"] == 890.0
    assert data["currency"] == "EUR"
    assert data["rating"] == 4.92
    assert len(data["images"]) == 5
    assert len(data["reviews"]) == 2


def test_get_tropical_villa(client: TestClient):
    """Test getting Tropical Paradise Villa by ID"""
    response = client.get(f"/api/v1/properties/{TROPICAL_VILLA_ID}")

    assert response.status_code == 200
    data = response.json()
    
    assert data["id"] == str(TROPICAL_VILLA_ID)
    assert data["name"] == "Villa Paraíso Tropical"
    assert data["location"] == "Bora Bora, French Polynesia"
    assert data["bedrooms"] == 4
    assert data["bathrooms"] == 4.0
    assert data["max_guests"] == 10
    assert data["price_per_night"] == 1650.0
    assert data["currency"] == "USD"
    assert data["rating"] == 4.99
    assert data["review_count"] == 89
    assert len(data["images"]) == 5
    assert len(data["reviews"]) == 2


def test_property_amenities_loaded_correctly(client: TestClient):
    """Test that amenities are correctly parsed from JSON"""
    response = client.get(f"/api/v1/properties/{RENAISSANCE_ESTATE_ID}")

    assert response.status_code == 200
    data = response.json()
    
    amenities = data["amenities"]
    assert isinstance(amenities, list)
    assert "Piscina Infinita Privada" in amenities
    assert len(amenities) == 8
