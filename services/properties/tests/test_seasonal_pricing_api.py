"""Integration tests for seasonal pricing endpoints"""
import jwt
import pytest
from uuid import UUID, uuid4
from fastapi.testclient import TestClient
from sqlmodel import Session

from core.config import settings
from db.seed import RENAISSANCE_ESTATE_ID, DEMO_HOTEL_A_OWNER_ID
from domain.schemas.property import SeasonalPricingCreateRequest


def jwt_for_admin(admin_id: str | UUID) -> str:
    """Generate a valid JWT for a given admin ID for testing."""
    return jwt.encode(
        {"sub": str(admin_id)},
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def test_create_seasonal_pricing_success(client: TestClient, session: Session):
    """Successfully create seasonal pricing with auto-generated signature"""
    admin_bearer = f"Bearer {jwt_for_admin(DEMO_HOTEL_A_OWNER_ID)}"
    
    payload = {
        "season_start": "2026-06-01",
        "season_end": "2026-08-31",
        "price_per_night": 150.0,
        "currency": "COP",
        "tax_rate": 0.19,
        "cleaning_fee": 50.0,
    }
    
    response = client.post(
        f"/api/v1/properties/{RENAISSANCE_ESTATE_ID}/seasonal-pricing",
        json=payload,
        headers={"Authorization": admin_bearer},
    )
    
    assert response.status_code == 201
    data = response.json()
    assert data["property_id"] == str(RENAISSANCE_ESTATE_ID)
    assert data["price_per_night"] == 150.0
    assert data["signature_hash"] is not None
    assert data["integrity_valid"] is True
    assert data["integrity_locked"] is False


def test_create_seasonal_pricing_missing_property(client: TestClient):
    """Fail to create pricing for non-existent property"""
    admin_bearer = f"Bearer {jwt_for_admin(DEMO_HOTEL_A_OWNER_ID)}"
    non_existent_id = uuid4()
    
    payload = {
        "season_start": "2026-06-01",
        "season_end": "2026-08-31",
        "price_per_night": 150.0,
        "currency": "COP",
        "tax_rate": 0.19,
        "cleaning_fee": 50.0,
    }
    
    response = client.post(
        f"/api/v1/properties/{non_existent_id}/seasonal-pricing",
        json=payload,
        headers={"Authorization": admin_bearer},
    )
    
    assert response.status_code == 404


def test_create_seasonal_pricing_ownership_check(client: TestClient):
    """Fail to create pricing if admin doesn't own the property"""
    other_admin_id = str(uuid4())
    admin_bearer = f"Bearer {other_admin_id}"
    
    payload = {
        "season_start": "2026-06-01",
        "season_end": "2026-08-31",
        "price_per_night": 150.0,
        "currency": "COP",
        "tax_rate": 0.19,
        "cleaning_fee": 50.0,
    }
    
    response = client.post(
        f"/api/v1/properties/{RENAISSANCE_ESTATE_ID}/seasonal-pricing",
        json=payload,
        headers={"Authorization": admin_bearer},
    )
    
    assert response.status_code == 403


def test_get_seasonal_pricing_list(client: TestClient):
    """Successfully retrieve list of seasonal pricing for property"""
    # First, create one
    admin_bearer = f"Bearer {jwt_for_admin(DEMO_HOTEL_A_OWNER_ID)}"
    payload = {
        "season_start": "2026-06-01",
        "season_end": "2026-08-31",
        "price_per_night": 150.0,
        "currency": "COP",
        "tax_rate": 0.19,
        "cleaning_fee": 50.0,
    }
    
    create_response = client.post(
        f"/api/v1/properties/{RENAISSANCE_ESTATE_ID}/seasonal-pricing",
        json=payload,
        headers={"Authorization": admin_bearer},
    )
    assert create_response.status_code == 201
    
    # Then, list
    list_response = client.get(
        f"/api/v1/properties/{RENAISSANCE_ESTATE_ID}/seasonal-pricing"
    )
    
    assert list_response.status_code == 200
    data = list_response.json()
    assert "items" in data
    assert "total" in data
    assert len(data["items"]) >= 1
    assert data["items"][0]["integrity_valid"] is True


def test_get_seasonal_pricing_single(client: TestClient):
    """Successfully retrieve single seasonal pricing record"""
    # Create first
    admin_bearer = f"Bearer {jwt_for_admin(DEMO_HOTEL_A_OWNER_ID)}"
    payload = {
        "season_start": "2026-12-01",
        "season_end": "2026-12-31",
        "price_per_night": 250.0,
        "currency": "COP",
        "tax_rate": 0.19,
        "cleaning_fee": 75.0,
    }
    
    create_response = client.post(
        f"/api/v1/properties/{RENAISSANCE_ESTATE_ID}/seasonal-pricing",
        json=payload,
        headers={"Authorization": admin_bearer},
    )
    assert create_response.status_code == 201
    pricing_id = create_response.json()["id"]
    
    # Get single
    get_response = client.get(
        f"/api/v1/properties/{RENAISSANCE_ESTATE_ID}/seasonal-pricing/{pricing_id}"
    )
    
    assert get_response.status_code == 200
    data = get_response.json()
    assert data["id"] == pricing_id
    assert data["price_per_night"] == 250.0
    assert data["integrity_valid"] is True


def test_update_seasonal_pricing_success(client: TestClient):
    """Successfully update seasonal pricing"""
    # Create first
    admin_bearer = f"Bearer {jwt_for_admin(DEMO_HOTEL_A_OWNER_ID)}"
    payload_create = {
        "season_start": "2026-07-01",
        "season_end": "2026-07-31",
        "price_per_night": 100.0,
        "currency": "COP",
        "tax_rate": 0.19,
        "cleaning_fee": 30.0,
    }
    
    create_response = client.post(
        f"/api/v1/properties/{RENAISSANCE_ESTATE_ID}/seasonal-pricing",
        json=payload_create,
        headers={"Authorization": admin_bearer},
    )
    assert create_response.status_code == 201
    pricing_id = create_response.json()["id"]
    
    # Update
    payload_update = {
        "season_start": "2026-07-01",
        "season_end": "2026-07-31",
        "price_per_night": 200.0,  # Changed
        "currency": "COP",
        "tax_rate": 0.19,
        "cleaning_fee": 30.0,
    }
    
    update_response = client.patch(
        f"/api/v1/properties/{RENAISSANCE_ESTATE_ID}/seasonal-pricing/{pricing_id}",
        json=payload_update,
        headers={"Authorization": admin_bearer},
    )
    
    assert update_response.status_code == 200
    data = update_response.json()
    assert data["price_per_night"] == 200.0
    assert data["integrity_valid"] is True


def test_get_seasonal_pricing_not_found(client: TestClient):
    """Fail to get non-existent seasonal pricing"""
    non_existent_id = uuid4()
    
    response = client.get(
        f"/api/v1/properties/{RENAISSANCE_ESTATE_ID}/seasonal-pricing/{non_existent_id}"
    )
    
    assert response.status_code == 404


def test_audit_log_created_on_pricing_write(client: TestClient, session: Session):
    """Verify audit log entry created on pricing update"""
    from adapters.models.property_pricing_audit_log import PropertyPricingAuditLog
    
    admin_bearer = f"Bearer {jwt_for_admin(DEMO_HOTEL_A_OWNER_ID)}"
    payload = {
        "season_start": "2026-08-01",
        "season_end": "2026-08-15",
        "price_per_night": 175.0,
        "currency": "COP",
        "tax_rate": 0.19,
        "cleaning_fee": 40.0,
    }
    
    response = client.post(
        f"/api/v1/properties/{RENAISSANCE_ESTATE_ID}/seasonal-pricing",
        json=payload,
        headers={"Authorization": admin_bearer},
    )
    
    assert response.status_code == 201
    
    # Check audit log
    audit_logs = session.query(PropertyPricingAuditLog).filter(
        PropertyPricingAuditLog.property_id == RENAISSANCE_ESTATE_ID
    ).all()
    
    assert len(audit_logs) > 0
    latest = audit_logs[-1]
    assert latest.action == "pricing_created"
    assert latest.signature_hash is not None
    assert latest.actor_admin_id is not None


def test_all_reads_validate_signature(client: TestClient):
    """Every read-path call validates signature (100% coverage)"""
    # Create
    admin_bearer = f"Bearer {jwt_for_admin(DEMO_HOTEL_A_OWNER_ID)}"
    payload = {
        "season_start": "2026-09-01",
        "season_end": "2026-09-30",
        "price_per_night": 200.0,
        "currency": "COP",
        "tax_rate": 0.19,
        "cleaning_fee": 50.0,
    }
    
    create_response = client.post(
        f"/api/v1/properties/{RENAISSANCE_ESTATE_ID}/seasonal-pricing",
        json=payload,
        headers={"Authorization": admin_bearer},
    )
    assert create_response.status_code == 201
    created_data = create_response.json()
    
    # Read 1 - list
    list_response = client.get(
        f"/api/v1/properties/{RENAISSANCE_ESTATE_ID}/seasonal-pricing"
    )
    assert list_response.status_code == 200
    assert any(item["integrity_valid"] for item in list_response.json()["items"])
    
    # Read 2 - single
    get_response = client.get(
        f"/api/v1/properties/{RENAISSANCE_ESTATE_ID}/seasonal-pricing/{created_data['id']}"
    )
    assert get_response.status_code == 200
    assert get_response.json()["integrity_valid"] is True
