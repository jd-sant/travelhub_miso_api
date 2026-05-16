from sqlmodel import Session, select

from adapters.models.user import User
from core.privacy import build_lookup_hash, decrypt_sensitive_value


def test_create_user_encrypts_pii_when_enabled(monkeypatch, client, test_engine):
    monkeypatch.setenv("USERS_PII_ENCRYPTION_ENABLED", "true")
    monkeypatch.setenv("USERS_PII_ENCRYPTION_KEY", "test-users-pii-key")
    monkeypatch.setenv("DATA_RESIDENCY_POLICIES", '{"CO":"aws-us-east-1","BR":"aws-sa-east-1"}')

    payload = {
        "email": "privada@example.com",
        "phone": "3001234567",
        "password": "miPasswordSegura123",
        "full_name": "Ana Privada",
        "country_code": "BR",
        "status": 1,
    }

    response = client.post("/api/v1/users", json=payload)

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == payload["email"]
    assert body["phone"] == payload["phone"]
    assert body["full_name"] == payload["full_name"]
    assert body["country_code"] == "BR"
    assert body["data_region"] == "aws-sa-east-1"

    with Session(test_engine) as session:
        stored_user = session.exec(
            select(User).where(User.email_lookup_hash == build_lookup_hash(payload["email"]))
        ).first()

    assert stored_user is not None
    assert stored_user.email != payload["email"]
    assert stored_user.phone != payload["phone"]
    assert stored_user.full_name != payload["full_name"]
    assert stored_user.email.startswith("enc:v1:")
    assert stored_user.pii_encrypted is True
    assert stored_user.email_lookup_hash == build_lookup_hash(payload["email"])
    assert decrypt_sensitive_value(stored_user.email, "test-users-pii-key") == payload["email"]


def test_duplicate_email_uses_lookup_hash_when_pii_is_encrypted(monkeypatch, client):
    monkeypatch.setenv("USERS_PII_ENCRYPTION_ENABLED", "true")
    monkeypatch.setenv("USERS_PII_ENCRYPTION_KEY", "test-users-pii-key")
    payload = {
        "email": "duplicada@example.com",
        "phone": "3001234567",
        "password": "miPasswordSegura123",
        "full_name": "Ana Duplicada",
        "country_code": "CO",
    }

    assert client.post("/api/v1/users", json=payload).status_code == 201
    response = client.post("/api/v1/users", json=payload)

    assert response.status_code == 409
