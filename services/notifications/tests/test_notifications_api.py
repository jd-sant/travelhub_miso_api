from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from adapters.models.notification import Notification
from adapters.models.notification_audit_log import NotificationAuditLog
from adapters.models.notification_delivery_attempt import NotificationDeliveryAttempt
from core.config import settings
from db.session import get_session
from entrypoints.api.main import create_application


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

    def override_get_session():
        with Session(test_engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    with TestClient(app) as test_client:
        yield test_client


def _payload():
    return {
        "reservation_id": str(uuid4()),
        "traveler_id": str(uuid4()),
        "payment_id": str(uuid4()),
        "recipient_email": "traveler@example.com",
        "recipient_name": "Ana Traveler",
        "property_name": "Hotel Central",
        "check_in_date": "2026-10-12",
        "check_out_date": "2026-10-17",
        "amount_in_cents": 287650,
        "currency": "COP",
        "receipt_id": str(uuid4()),
        "receipt_number": "RCPT-20261012-101010",
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


def test_get_notification_returns_created_notification(client):
    create_response = client.post(
        "/api/v1/internal/payment-confirmations",
        json=_payload(),
        headers={"X-Internal-Api-Key": settings.internal_api_key},
    )

    notification_id = create_response.json()["notification_id"]
    response = client.get(f"/api/v1/notifications/{notification_id}")

    assert response.status_code == 200
    assert response.json()["notification_id"] == notification_id
