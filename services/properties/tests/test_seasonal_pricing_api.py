"""Integration tests for seasonal pricing endpoints"""
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from adapters.models.property_pricing_audit_log import PropertyPricingAuditLog
from adapters.models.property_seasonal_price import PropertySeasonalPrice
from db.seed import DEMO_HOTEL_A_OWNER_ID, RENAISSANCE_ESTATE_ID

from tests.conftest import bearer_for_admin


def _payload(**overrides):
    base = {
        "season_start": "2026-06-01",
        "season_end": "2026-08-31",
        "price_per_night": 150.0,
        "currency": "COP",
        "tax_rate": 0.19,
        "cleaning_fee": 50.0,
    }
    base.update(overrides)
    return base


def test_create_seasonal_pricing_success(client: TestClient):
    response = client.post(
        f"/api/v1/properties/{RENAISSANCE_ESTATE_ID}/seasonal-pricing",
        json=_payload(),
        headers={"Authorization": bearer_for_admin(DEMO_HOTEL_A_OWNER_ID)},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["property_id"] == str(RENAISSANCE_ESTATE_ID)
    assert data["price_per_night"] == 150.0
    assert data["signature_hash"]
    assert data["integrity_valid"] is True
    assert data["integrity_locked"] is False
    assert data["season_start"] == "2026-06-01"  # ISO contract preserved


def test_create_seasonal_pricing_missing_property(client: TestClient):
    response = client.post(
        f"/api/v1/properties/{uuid4()}/seasonal-pricing",
        json=_payload(),
        headers={"Authorization": bearer_for_admin(DEMO_HOTEL_A_OWNER_ID)},
    )
    assert response.status_code == 404


def test_create_seasonal_pricing_ownership_check(client: TestClient):
    response = client.post(
        f"/api/v1/properties/{RENAISSANCE_ESTATE_ID}/seasonal-pricing",
        json=_payload(),
        headers={"Authorization": bearer_for_admin(uuid4())},
    )
    assert response.status_code == 403


def test_create_seasonal_pricing_unauthenticated(client: TestClient):
    """Without Bearer token, endpoint replies 401."""
    response = client.post(
        f"/api/v1/properties/{RENAISSANCE_ESTATE_ID}/seasonal-pricing",
        json=_payload(),
    )
    assert response.status_code == 401


def test_create_seasonal_pricing_invalid_token(client: TestClient):
    """Invalid bearer (not parseable as UUID by the fake) → 401."""
    response = client.post(
        f"/api/v1/properties/{RENAISSANCE_ESTATE_ID}/seasonal-pricing",
        json=_payload(),
        headers={"Authorization": "Bearer not-a-uuid"},
    )
    assert response.status_code == 401


def test_get_seasonal_pricing_list(client: TestClient):
    headers = {"Authorization": bearer_for_admin(DEMO_HOTEL_A_OWNER_ID)}
    create_response = client.post(
        f"/api/v1/properties/{RENAISSANCE_ESTATE_ID}/seasonal-pricing",
        json=_payload(),
        headers=headers,
    )
    assert create_response.status_code == 201

    list_response = client.get(
        f"/api/v1/properties/{RENAISSANCE_ESTATE_ID}/seasonal-pricing"
    )
    assert list_response.status_code == 200
    data = list_response.json()
    assert "items" in data
    assert "total" in data
    assert data["total"] >= 1
    assert data["items"][0]["integrity_valid"] is True


def test_get_seasonal_pricing_single(client: TestClient):
    headers = {"Authorization": bearer_for_admin(DEMO_HOTEL_A_OWNER_ID)}
    create_response = client.post(
        f"/api/v1/properties/{RENAISSANCE_ESTATE_ID}/seasonal-pricing",
        json=_payload(season_start="2026-12-01", season_end="2026-12-31", price_per_night=250.0),
        headers=headers,
    )
    pricing_id = create_response.json()["id"]

    get_response = client.get(
        f"/api/v1/properties/{RENAISSANCE_ESTATE_ID}/seasonal-pricing/{pricing_id}"
    )
    assert get_response.status_code == 200
    data = get_response.json()
    assert data["id"] == pricing_id
    assert data["price_per_night"] == 250.0
    assert data["integrity_valid"] is True


def test_update_seasonal_pricing_full_payload(client: TestClient):
    headers = {"Authorization": bearer_for_admin(DEMO_HOTEL_A_OWNER_ID)}
    create_response = client.post(
        f"/api/v1/properties/{RENAISSANCE_ESTATE_ID}/seasonal-pricing",
        json=_payload(season_start="2026-07-01", season_end="2026-07-31", price_per_night=100.0),
        headers=headers,
    )
    pricing_id = create_response.json()["id"]

    update_response = client.patch(
        f"/api/v1/properties/{RENAISSANCE_ESTATE_ID}/seasonal-pricing/{pricing_id}",
        json=_payload(season_start="2026-07-01", season_end="2026-07-31", price_per_night=200.0),
        headers=headers,
    )
    assert update_response.status_code == 200
    assert update_response.json()["price_per_night"] == 200.0


def test_update_seasonal_pricing_partial_payload(client: TestClient):
    """PATCH with only one field updates that field, regenerates signature, leaves rest intact."""
    headers = {"Authorization": bearer_for_admin(DEMO_HOTEL_A_OWNER_ID)}
    create_response = client.post(
        f"/api/v1/properties/{RENAISSANCE_ESTATE_ID}/seasonal-pricing",
        json=_payload(price_per_night=120.0, cleaning_fee=10.0),
        headers=headers,
    )
    created = create_response.json()
    pricing_id = created["id"]
    original_signature = created["signature_hash"]

    update_response = client.patch(
        f"/api/v1/properties/{RENAISSANCE_ESTATE_ID}/seasonal-pricing/{pricing_id}",
        json={"price_per_night": 175.0},  # only one field
        headers=headers,
    )
    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["price_per_night"] == 175.0
    assert updated["cleaning_fee"] == 10.0  # untouched
    assert updated["signature_hash"] != original_signature  # re-signed


def test_get_seasonal_pricing_not_found(client: TestClient):
    response = client.get(
        f"/api/v1/properties/{RENAISSANCE_ESTATE_ID}/seasonal-pricing/{uuid4()}"
    )
    assert response.status_code == 404


def test_audit_log_created_on_pricing_write(client: TestClient, session: Session):
    headers = {"Authorization": bearer_for_admin(DEMO_HOTEL_A_OWNER_ID)}
    response = client.post(
        f"/api/v1/properties/{RENAISSANCE_ESTATE_ID}/seasonal-pricing",
        json=_payload(season_start="2026-08-01", season_end="2026-08-15", price_per_night=175.0),
        headers=headers,
    )
    assert response.status_code == 201

    audit_logs = session.query(PropertyPricingAuditLog).filter(
        PropertyPricingAuditLog.property_id == RENAISSANCE_ESTATE_ID
    ).all()
    assert audit_logs
    latest = audit_logs[-1]
    assert latest.action == "pricing_created"
    assert latest.signature_hash
    assert latest.actor_admin_id == str(DEMO_HOTEL_A_OWNER_ID)


def test_audit_log_records_x_forwarded_for(client: TestClient, session: Session):
    headers = {
        "Authorization": bearer_for_admin(DEMO_HOTEL_A_OWNER_ID),
        "X-Forwarded-For": "203.0.113.7, 10.0.0.1",
    }
    response = client.post(
        f"/api/v1/properties/{RENAISSANCE_ESTATE_ID}/seasonal-pricing",
        json=_payload(season_start="2026-09-01", season_end="2026-09-15"),
        headers=headers,
    )
    assert response.status_code == 201

    latest = session.query(PropertyPricingAuditLog).order_by(
        PropertyPricingAuditLog.created_at.desc()
    ).first()
    assert latest is not None
    assert latest.source_ip == "203.0.113.7"


def test_all_reads_validate_signature(client: TestClient):
    headers = {"Authorization": bearer_for_admin(DEMO_HOTEL_A_OWNER_ID)}
    create_response = client.post(
        f"/api/v1/properties/{RENAISSANCE_ESTATE_ID}/seasonal-pricing",
        json=_payload(season_start="2026-10-01", season_end="2026-10-30", price_per_night=200.0),
        headers=headers,
    )
    pricing_id = create_response.json()["id"]

    list_response = client.get(
        f"/api/v1/properties/{RENAISSANCE_ESTATE_ID}/seasonal-pricing"
    )
    assert list_response.status_code == 200
    assert all(item["integrity_valid"] for item in list_response.json()["items"])

    get_response = client.get(
        f"/api/v1/properties/{RENAISSANCE_ESTATE_ID}/seasonal-pricing/{pricing_id}"
    )
    assert get_response.status_code == 200
    assert get_response.json()["integrity_valid"] is True


def test_get_locks_record_when_tampered(client: TestClient, session: Session):
    """Mutating the row out-of-band should be detected on next read and lock the record."""
    headers = {"Authorization": bearer_for_admin(DEMO_HOTEL_A_OWNER_ID)}
    create_response = client.post(
        f"/api/v1/properties/{RENAISSANCE_ESTATE_ID}/seasonal-pricing",
        json=_payload(season_start="2026-11-01", season_end="2026-11-30", price_per_night=100.0),
        headers=headers,
    )
    pricing_id = UUID(create_response.json()["id"])

    # Out-of-band tampering: change the price without updating the signature.
    row = session.query(PropertySeasonalPrice).filter(
        PropertySeasonalPrice.id == pricing_id
    ).one()
    row.price_per_night = 1.0
    session.add(row)
    session.commit()

    get_response = client.get(
        f"/api/v1/properties/{RENAISSANCE_ESTATE_ID}/seasonal-pricing/{pricing_id}"
    )
    assert get_response.status_code == 200
    body = get_response.json()
    assert body["integrity_valid"] is False
    assert body["integrity_locked"] is True

    # Audit log records the integrity_failed event.
    failed_events = session.query(PropertyPricingAuditLog).filter(
        PropertyPricingAuditLog.action == "integrity_failed",
        PropertyPricingAuditLog.seasonal_price_id == pricing_id,
    ).all()
    assert len(failed_events) == 1


def test_locked_record_rejects_update_with_423(client: TestClient, session: Session):
    headers = {"Authorization": bearer_for_admin(DEMO_HOTEL_A_OWNER_ID)}
    create_response = client.post(
        f"/api/v1/properties/{RENAISSANCE_ESTATE_ID}/seasonal-pricing",
        json=_payload(season_start="2026-04-01", season_end="2026-04-30"),
        headers=headers,
    )
    pricing_id = UUID(create_response.json()["id"])

    row = session.query(PropertySeasonalPrice).filter(
        PropertySeasonalPrice.id == pricing_id
    ).one()
    row.integrity_locked = True
    session.add(row)
    session.commit()

    response = client.patch(
        f"/api/v1/properties/{RENAISSANCE_ESTATE_ID}/seasonal-pricing/{pricing_id}",
        json={"price_per_night": 999.0},
        headers=headers,
    )
    assert response.status_code == 423


def test_unlock_endpoint_clears_lock_and_records_audit(client: TestClient, session: Session):
    headers = {"Authorization": bearer_for_admin(DEMO_HOTEL_A_OWNER_ID)}
    create_response = client.post(
        f"/api/v1/properties/{RENAISSANCE_ESTATE_ID}/seasonal-pricing",
        json=_payload(season_start="2026-05-01", season_end="2026-05-31", price_per_night=120.0),
        headers=headers,
    )
    pricing_id = UUID(create_response.json()["id"])

    # Simulate out-of-band tampering + lock (as would happen after an integrity_failed event).
    row = session.query(PropertySeasonalPrice).filter(
        PropertySeasonalPrice.id == pricing_id
    ).one()
    row.price_per_night = 999.0  # tampered value
    row.integrity_locked = True
    original_signature = row.signature_hash
    session.add(row)
    session.commit()

    unlock_response = client.post(
        f"/api/v1/properties/{RENAISSANCE_ESTATE_ID}/seasonal-pricing/{pricing_id}/unlock",
        json={"reason": "Reviewed manually after audit ticket #99"},
        headers=headers,
    )
    assert unlock_response.status_code == 200
    body = unlock_response.json()
    assert body["integrity_locked"] is False
    # Signature regenerated from current (tampered) state, so it differs from the original.
    assert body["signature_hash"] != original_signature

    # Subsequent read confirms integrity is now valid against the current state.
    follow_up = client.get(
        f"/api/v1/properties/{RENAISSANCE_ESTATE_ID}/seasonal-pricing/{pricing_id}"
    )
    assert follow_up.status_code == 200
    assert follow_up.json()["integrity_valid"] is True

    audit = session.query(PropertyPricingAuditLog).filter(
        PropertyPricingAuditLog.action == "pricing_unlocked",
        PropertyPricingAuditLog.seasonal_price_id == pricing_id,
    ).all()
    assert len(audit) == 1
    assert audit[0].actor_admin_id == str(DEMO_HOTEL_A_OWNER_ID)


def test_unlock_requires_reason_min_length(client: TestClient):
    headers = {"Authorization": bearer_for_admin(DEMO_HOTEL_A_OWNER_ID)}
    create_response = client.post(
        f"/api/v1/properties/{RENAISSANCE_ESTATE_ID}/seasonal-pricing",
        json=_payload(season_start="2026-03-01", season_end="2026-03-31"),
        headers=headers,
    )
    pricing_id = create_response.json()["id"]

    response = client.post(
        f"/api/v1/properties/{RENAISSANCE_ESTATE_ID}/seasonal-pricing/{pricing_id}/unlock",
        json={"reason": "short"},
        headers=headers,
    )
    assert response.status_code == 422


def test_unlock_enforces_ownership(client: TestClient):
    headers = {"Authorization": bearer_for_admin(DEMO_HOTEL_A_OWNER_ID)}
    create_response = client.post(
        f"/api/v1/properties/{RENAISSANCE_ESTATE_ID}/seasonal-pricing",
        json=_payload(season_start="2026-02-01", season_end="2026-02-28"),
        headers=headers,
    )
    pricing_id = create_response.json()["id"]

    response = client.post(
        f"/api/v1/properties/{RENAISSANCE_ESTATE_ID}/seasonal-pricing/{pricing_id}/unlock",
        json={"reason": "Trying to unlock without owning the property"},
        headers={"Authorization": bearer_for_admin(uuid4())},
    )
    assert response.status_code == 403
