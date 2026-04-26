"""Tests for seeded data and endpoints"""
import uuid

from fastapi.testclient import TestClient
from sqlmodel import Session

from db.seed import (
    ALPINE_LODGE_ID,
    BEACHFRONT_PENTHOUSE_ID,
    CIKOS_EXECUTIVE_SUITES_ID,
    RENAISSANCE_ESTATE_ID,
    TROPICAL_VILLA_ID,
)


def test_list_properties_returns_seeded_data(
    client: TestClient, session: Session
):
    """Test that list_properties returns all 5 seeded properties"""
    response = client.get("/api/v1/properties")

    assert response.status_code == 200
    data = response.json()

    assert len(data) == 5

    names = {prop["name"] for prop in data}
    expected_names = {
        "Mansión Renacentista & Viñedo Privado",
        "Penthouse Moderno Frente a la Playa",
        "Refugio Alpino de Montaña",
        "Villa Paraíso Tropical",
        "Hotel Cikos Executive Suites",
    }
    assert names == expected_names
    assert str(CIKOS_EXECUTIVE_SUITES_ID) in {prop["id"] for prop in data}


def test_get_renaissance_estate(client: TestClient):
    """Test getting Renaissance Estate by ID"""
    response = client.get(f"/api/v1/properties/{RENAISSANCE_ESTATE_ID}")

    assert response.status_code == 200
    data = response.json()

    assert data["id"] == str(RENAISSANCE_ESTATE_ID)
    assert data["name"] == "Mansión Renacentista & Viñedo Privado"
    assert data["location"] == "Fiesole, Florencia"
    assert data["bedrooms"] == 4
    assert data["bathrooms"] == 4.5
    assert data["max_guests"] == 12
    assert data["price_per_night"] == 1240.0
    assert data["currency"] == "COP"
    assert data["rating"] == 4.98
    assert data["review_count"] == 54

    assert len(data["images"]) == 5
    assert data["images"][0]["position"] == 0
    assert (
        data["images"][0]["url"]
        == "https://images.unsplash.com/photo-1564013799919-ab600027ffc6?w=800&q=80"
    )
    assert (
        data["images"][0]["url_hires"]
        == "https://images.unsplash.com/photo-1564013799919-ab600027ffc6?w=1920&q=90"
    )
    assert data["images"][0]["is_cover"] is True

    assert len(data["reviews"]) == 2
    assert data["reviews"][0]["author"] == "María González"
    assert data["reviews"][0]["rating"] == 5

    assert data["cancellation_policy"] != ""
    assert data["tax_rate"] == 0.19
    assert data["cleaning_fee"] == 120.0


def test_get_beachfront_penthouse(client: TestClient):
    """Test getting Modern Beachfront Penthouse by ID"""
    response = client.get(f"/api/v1/properties/{BEACHFRONT_PENTHOUSE_ID}")

    assert response.status_code == 200
    data = response.json()

    assert data["id"] == str(BEACHFRONT_PENTHOUSE_ID)
    assert data["name"] == "Penthouse Moderno Frente a la Playa"
    assert data["location"] == "Playa Miami, Florida"
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
    assert data["location"] == "Chamonix, Alpes Franceses"
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
    assert data["location"] == "Bora Bora, Polinesia Francesa"
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
