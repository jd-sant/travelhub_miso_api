from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from adapters.models.sensitive_data_audit_log import SensitiveDataAuditLog
from core.privacy import decrypt_sensitive_value, encrypt_sensitive_value, resolve_data_region
from db.session import get_session
from entrypoints.api.routers.privacy import router as privacy_router


def test_encrypt_sensitive_value_uses_aes_gcm_roundtrip() -> None:
    secret = "test-pii-key"
    encrypted = encrypt_sensitive_value("ana@example.com", secret)

    assert encrypted is not None
    assert encrypted.startswith("enc:v1:")
    assert encrypted != "ana@example.com"
    assert decrypt_sensitive_value(encrypted, secret) == "ana@example.com"


def test_residency_policy_resolves_country_specific_region() -> None:
    region = resolve_data_region(
        "BR",
        policies={"BR": "aws-sa-east-1"},
        default_region="aws-us-east-1",
    )

    assert region == "aws-sa-east-1"


def test_internal_privacy_audit_records_hash_chain(test_engine) -> None:
    app = FastAPI()
    app.include_router(privacy_router, prefix="/api/v1")

    def override_get_session():
        with Session(test_engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    client = TestClient(app)
    actor_id = uuid4()

    first = client.post(
        "/api/v1/internal/privacy/audit",
        headers={"X-Internal-Api-Key": "test-internal-key"},
        json={
            "actor_user_id": str(actor_id),
            "action": "user.pii.accessed",
            "resource_type": "user",
            "resource_id": "user-1",
            "pii_fields": ["email", "phone", "email"],
            "source_ip": "10.0.0.8",
            "country_code": "CO",
            "metadata": {"channel": "admin_console"},
        },
    )
    second = client.post(
        "/api/v1/internal/privacy/audit",
        headers={"X-Internal-Api-Key": "test-internal-key"},
        json={
            "actor_user_id": str(actor_id),
            "action": "user.pii.exported",
            "resource_type": "user",
            "resource_id": "bulk",
            "pii_fields": ["full_name"],
            "source_ip": "10.0.0.8",
            "country_code": "BR",
        },
    )

    assert first.status_code == 201
    assert second.status_code == 201
    first_body = first.json()
    second_body = second.json()
    assert first_body["pii_fields"] == ["email", "phone"]
    assert first_body["previous_hash"] is None
    assert second_body["previous_hash"] == first_body["entry_hash"]
    assert second_body["data_region"] == "aws-sa-east-1"

    with Session(test_engine) as session:
        rows = session.exec(select(SensitiveDataAuditLog)).all()
        assert len(rows) == 2
        assert {row.action for row in rows} == {"user.pii.accessed", "user.pii.exported"}


def test_internal_privacy_audit_rejects_invalid_api_key(test_engine) -> None:
    app = FastAPI()
    app.include_router(privacy_router, prefix="/api/v1")

    def override_get_session():
        with Session(test_engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    client = TestClient(app)

    response = client.post(
        "/api/v1/internal/privacy/audit",
        headers={"X-Internal-Api-Key": "wrong"},
        json={
            "action": "user.pii.accessed",
            "resource_type": "user",
            "pii_fields": ["email"],
            "source_ip": "10.0.0.8",
        },
    )

    assert response.status_code == 403
