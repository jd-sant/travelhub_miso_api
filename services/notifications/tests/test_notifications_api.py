from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from adapters.models.notification import Notification
from adapters.models.notification_audit_log import NotificationAuditLog
from adapters.models.notification_delivery_attempt import NotificationDeliveryAttempt
from assembly import (
    get_payment_confirmation_source,
    get_traveler_profile_source,
)
from core.config import settings
from db.session import get_session
from domain.schemas.notification import PaymentConfirmationSourceRecord, TravelerProfileRecord
from entrypoints.api.main import create_application


class FakePaymentConfirmationSource:
    def __init__(self):
        self.record = PaymentConfirmationSourceRecord(
            payment_id=uuid4(),
            reservation_id=uuid4(),
            traveler_id=uuid4(),
            status="confirmed",
            amount_in_cents=287650,
            currency="COP",
            receipt_id=uuid4(),
            receipt_number="RCPT-20261012-101010",
            property_name="Hotel Central",
            check_in_date="2026-10-12",
            check_out_date="2026-10-17",
        )

    def get_confirmation(self, payment_id):
        return self.record.model_copy(update={"payment_id": payment_id})


class FakeTravelerProfileSource:
    def get_traveler(self, traveler_id):
        return TravelerProfileRecord(
            traveler_id=traveler_id,
            email="traveler@example.com",
            full_name="Ana Traveler",
        )


@pytest.fixture
def test_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture
def client(test_engine, monkeypatch):
    monkeypatch.setenv("SKIP_DB_INIT_ON_STARTUP", "True")
    app = create_application()
    payment_source = FakePaymentConfirmationSource()

    def override_get_session():
        with Session(test_engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_payment_confirmation_source] = lambda: payment_source
    app.dependency_overrides[get_traveler_profile_source] = lambda: FakeTravelerProfileSource()
    with TestClient(app) as test_client:
        yield test_client


def _payload():
    return {
        "payment_id": str(uuid4()),
        "source_ip": "127.0.0.1",
    }


def test_create_payment_confirmation_persists_notification_and_audit(client, test_engine):
    response = client.post(
        "/api/v1/internal/payment-confirmations",
        json=_payload(),
        headers={"X-Internal-Api-Key": settings.internal_api_key},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "sent"

    with Session(test_engine) as session:
        notifications = session.exec(select(Notification)).all()
        attempts = session.exec(select(NotificationDeliveryAttempt)).all()
        audits = session.exec(select(NotificationAuditLog)).all()

    assert len(notifications) == 1
    assert len(attempts) == 1
    assert len(audits) == 2
    assert "traveler" not in notifications[0].payload
    assert "payment_confirmation" not in notifications[0].payload
    assert notifications[0].payload == {
        "payment_summary": {
            "payment_id": notifications[0].payload["payment_summary"]["payment_id"],
            "reservation_id": notifications[0].payload["payment_summary"]["reservation_id"],
            "traveler_id": notifications[0].payload["payment_summary"]["traveler_id"],
            "status": "confirmed",
            "amount_in_cents": 287650,
            "currency": "COP",
            "receipt_id": notifications[0].payload["payment_summary"]["receipt_id"],
            "receipt_number": "RCPT-20261012-101010",
            "property_name": "Hotel Central",
            "check_in_date": "2026-10-12",
            "check_out_date": "2026-10-17",
        },
        "recipient": {
            "email_masked": "t***r@example.com",
        },
    }


def test_get_notification_returns_created_notification(client):
    create_response = client.post(
        "/api/v1/internal/payment-confirmations",
        json=_payload(),
        headers={"X-Internal-Api-Key": settings.internal_api_key},
    )

    notification_id = create_response.json()["notification_id"]
    response = client.get(
        f"/api/v1/notifications/{notification_id}",
        headers={"X-Internal-Api-Key": settings.internal_api_key},
    )

    assert response.status_code == 200
    assert response.json()["notification_id"] == notification_id


def test_get_notification_requires_internal_api_key(client):
    create_response = client.post(
        "/api/v1/internal/payment-confirmations",
        json=_payload(),
        headers={"X-Internal-Api-Key": settings.internal_api_key},
    )

    notification_id = create_response.json()["notification_id"]
    response = client.get(f"/api/v1/notifications/{notification_id}")

    assert response.status_code == 403


def test_create_payment_confirmation_is_idempotent_by_payment_id(client, test_engine):
    payload = _payload()

    first_response = client.post(
        "/api/v1/internal/payment-confirmations",
        json=payload,
        headers={"X-Internal-Api-Key": settings.internal_api_key},
    )
    second_response = client.post(
        "/api/v1/internal/payment-confirmations",
        json=payload,
        headers={"X-Internal-Api-Key": settings.internal_api_key},
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 201
    assert first_response.json()["notification_id"] == second_response.json()["notification_id"]

    with Session(test_engine) as session:
        notifications = session.exec(select(Notification)).all()

    assert len(notifications) == 1
