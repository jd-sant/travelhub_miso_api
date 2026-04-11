from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine, select

from adapters.models.payment_audit_log import PaymentAuditLog
from adapters.repositories.payment_audit_repository import SQLModelPaymentAuditRepository
from core.config import Settings
from core.security import (
    decrypt_sensitive_value,
    encrypt_sensitive_value,
    sanitize_sensitive_data,
)
from domain.schemas.audit import PaymentAuditLogRecord


@pytest.fixture
def test_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    try:
        yield engine
    finally:
        SQLModel.metadata.drop_all(engine)
        engine.dispose()


def test_encrypt_sensitive_value_roundtrip() -> None:
    secret = "test-encryption-secret"
    plaintext = "ctoken_test_confirmation"

    encrypted = encrypt_sensitive_value(plaintext, secret)

    assert encrypted is not None
    assert encrypted != plaintext
    assert encrypted.startswith("enc:v1:")
    assert decrypt_sensitive_value(encrypted, secret) == plaintext


def test_sanitize_sensitive_data_redacts_known_financial_fields() -> None:
    payload = {
        "confirmation_token_id": "ctoken_123",
        "nested": {
            "payment_method_token": "pm_123",
            "card_number": "4242424242424242",
        },
    }

    sanitized = sanitize_sensitive_data(payload)

    assert sanitized == {
        "confirmation_token_id": "[REDACTED]",
        "nested": {
            "payment_method_token": "[REDACTED]",
            "card_number": "[REDACTED]",
        },
    }


def test_payment_audit_repository_sanitizes_payload(test_engine) -> None:
    with Session(test_engine) as session:
        repository = SQLModelPaymentAuditRepository(session)
        repository.add_log(
            PaymentAuditLogRecord(
                entity_type="payment",
                entity_id="payment-1",
                action="security.test",
                payload={
                    "confirmation_token_id": "ctoken_123",
                    "payment_method_token": "pm_123",
                },
                created_at=datetime.now(timezone.utc),
            )
        )
        stored_payload = session.exec(select(PaymentAuditLog)).first().payload

    assert stored_payload == {
        "confirmation_token_id": "[REDACTED]",
        "payment_method_token": "[REDACTED]",
    }


def test_settings_require_stripe_provider_in_compliance_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("PAYMENTS_COMPLIANCE_MODE", "true")
    monkeypatch.setenv("PAYMENT_PROVIDER", "fake_stripe")

    with pytest.raises(RuntimeError, match="stripe_test"):
        Settings().payment_provider


def test_settings_require_encryption_key_in_compliance_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("PAYMENTS_COMPLIANCE_MODE", "true")
    monkeypatch.setenv("PAYMENT_PROVIDER", "stripe_test")
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_example")
    monkeypatch.setenv("STRIPE_PUBLISHABLE_KEY", "pk_test_example")
    monkeypatch.delenv("PAYMENTS_DATA_ENCRYPTION_KEY", raising=False)

    with pytest.raises(RuntimeError, match="PAYMENTS_DATA_ENCRYPTION_KEY"):
        Settings().payments_data_encryption_key


def test_settings_require_notifications_service_url_in_compliance_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("PAYMENTS_COMPLIANCE_MODE", "true")
    monkeypatch.setenv("PAYMENT_PROVIDER", "stripe_test")
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_example")
    monkeypatch.setenv("STRIPE_PUBLISHABLE_KEY", "pk_test_example")
    monkeypatch.setenv("PAYMENTS_DATA_ENCRYPTION_KEY", "test-encryption-key")
    monkeypatch.delenv("NOTIFICATIONS_SERVICE_URL", raising=False)

    with pytest.raises(RuntimeError, match="NOTIFICATIONS_SERVICE_URL"):
        Settings().notifications_service_url


def test_backend_source_has_no_hardcoded_pan_literals() -> None:
    service_root = Path(__file__).resolve().parents[1]
    repo_root = Path(__file__).resolve().parents[3]
    target_files = list((service_root / "src").rglob("*.py"))
    target_files.append(repo_root / ".env.example")
    known_pan_literals = {
        "4242 4242 4242 4242",
        "4000 0000 0000 9995",
        "4000 0000 0000 0002",
        "4242424242424242",
        "4000000000009995",
        "4000000000000002",
    }

    offending = []
    for path in target_files:
        content = path.read_text(encoding="utf-8")
        if any(literal in content for literal in known_pan_literals):
            offending.append(str(path))

    assert offending == []
