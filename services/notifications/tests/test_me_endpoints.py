"""Tests de los endpoints mobile-facing /api/v1/me/*.

Cubre auth JWT, registro/revocación de devices, preferencias y listado/marca
de notificaciones desde el log de auditoría.
"""
import os

os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret-for-me-endpoints")

from datetime import datetime, timezone
from uuid import uuid4

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from adapters.auth.jwt_auth import current_user
from adapters.models.device_token import DeviceToken
from adapters.models.notification_audit_log import NotificationAuditLog
from adapters.models.notification_preference import NotificationPreference
from core.config import settings
from db.session import get_session
from entrypoints.api.main import create_application


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


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


@pytest.fixture
def user_id():
    return uuid4()


@pytest.fixture
def jwt_token(user_id):
    return jwt.encode({"sub": str(user_id)}, settings.jwt_secret_key, algorithm="HS256")


@pytest.fixture
def auth_headers(jwt_token):
    return {"Authorization": f"Bearer {jwt_token}"}


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


# ---------------------------------------------------------------------------
# /me/devices
# ---------------------------------------------------------------------------


def test_register_device_returns_401_without_authorization(client):
    response = client.post(
        "/api/v1/me/devices",
        json={"token": "x" * 32, "platform": "android"},
    )
    assert response.status_code == 401


def test_register_device_returns_401_with_invalid_token(client):
    response = client.post(
        "/api/v1/me/devices",
        json={"token": "x" * 32, "platform": "android"},
        headers={"Authorization": "Bearer not.a.real.jwt"},
    )
    assert response.status_code == 401


def test_register_device_persists_token(client, auth_headers, test_engine, user_id):
    response = client.post(
        "/api/v1/me/devices",
        json={"token": "fcm-token-abcdefghij", "platform": "android", "app_version": "1.2.3"},
        headers=auth_headers,
    )
    assert response.status_code == 201
    with Session(test_engine) as session:
        rows = session.exec(select(DeviceToken)).all()
    assert len(rows) == 1
    assert rows[0].token == "fcm-token-abcdefghij"
    assert rows[0].user_id == user_id
    assert rows[0].revoked_at is None


def test_register_device_is_idempotent(client, auth_headers, test_engine):
    payload = {"token": "fcm-token-same-aaaaa", "platform": "android"}
    client.post("/api/v1/me/devices", json=payload, headers=auth_headers)
    client.post("/api/v1/me/devices", json=payload, headers=auth_headers)
    with Session(test_engine) as session:
        rows = session.exec(select(DeviceToken)).all()
    assert len(rows) == 1


def test_revoke_device_marks_revoked_at(client, auth_headers, test_engine):
    client.post(
        "/api/v1/me/devices",
        json={"token": "to-be-revoked-12345", "platform": "android"},
        headers=auth_headers,
    )
    response = client.delete(
        "/api/v1/me/devices/to-be-revoked-12345", headers=auth_headers
    )
    assert response.status_code == 204
    with Session(test_engine) as session:
        row = session.exec(select(DeviceToken)).first()
    assert row.revoked_at is not None


# ---------------------------------------------------------------------------
# /me/notification-preferences
# ---------------------------------------------------------------------------


def test_get_preferences_returns_defaults_when_missing(client, auth_headers):
    response = client.get("/api/v1/me/notification-preferences", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["status_changes_enabled"] is True
    assert body["arrival_reminders_enabled"] is True


def test_patch_preferences_persists_and_returns_updated_values(
    client, auth_headers, test_engine, user_id
):
    response = client.patch(
        "/api/v1/me/notification-preferences",
        json={"status_changes_enabled": False},
        headers=auth_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status_changes_enabled"] is False
    assert body["arrival_reminders_enabled"] is True

    with Session(test_engine) as session:
        row = session.exec(
            select(NotificationPreference).where(NotificationPreference.user_id == user_id)
        ).first()
    assert row is not None
    assert row.status_changes_enabled is False


# ---------------------------------------------------------------------------
# /me/notifications + opened
# ---------------------------------------------------------------------------


def _seed_audit(session: Session, user_id, *, action: str, opened: bool = False):
    log = NotificationAuditLog(
        notification_id=uuid4(),
        traveler_id=user_id,
        entity_type="reservation",
        entity_id=str(uuid4()),
        action=action,
        payload={"title": "Reserva confirmada", "body": "ok"},
        created_at=datetime.now(timezone.utc),
        channel="push",
        delivery_status="opened" if opened else "sent",
        opened_at=datetime.now(timezone.utc) if opened else None,
    )
    session.add(log)
    session.commit()
    session.refresh(log)
    return log


def test_list_notifications_returns_only_user_push_audits(
    client, auth_headers, test_engine, user_id
):
    other_user = uuid4()
    with Session(test_engine) as session:
        _seed_audit(session, user_id, action="notification.reservation_event.booking_confirmed.push_dispatched")
        _seed_audit(session, other_user, action="notification.reservation_event.booking_confirmed.push_dispatched")

    response = client.get("/api/v1/me/notifications", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["title"] == "Reserva confirmada"
    assert body["items"][0]["is_read"] is False


def test_list_notifications_unread_filter_excludes_opened(
    client, auth_headers, test_engine, user_id
):
    with Session(test_engine) as session:
        _seed_audit(
            session,
            user_id,
            action="notification.reservation_event.booking_confirmed.push_dispatched",
            opened=False,
        )
        _seed_audit(
            session,
            user_id,
            action="notification.reservation_event.modification_confirmed.push_dispatched",
            opened=True,
        )

    response = client.get(
        "/api/v1/me/notifications?filter=unread", headers=auth_headers
    )
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["is_read"] is False


def test_mark_opened_sets_opened_at_and_is_idempotent(
    client, auth_headers, test_engine, user_id
):
    with Session(test_engine) as session:
        log = _seed_audit(
            session, user_id, action="notification.reservation_event.booking_confirmed.push_dispatched"
        )
        audit_id = log.id

    response = client.post(
        f"/api/v1/me/notifications/{audit_id}/opened", headers=auth_headers
    )
    assert response.status_code == 200
    first_opened_at = response.json()["opened_at"]
    assert first_opened_at is not None

    response2 = client.post(
        f"/api/v1/me/notifications/{audit_id}/opened", headers=auth_headers
    )
    assert response2.status_code == 200
    # idempotente: no cambia el opened_at original
    assert response2.json()["opened_at"] == first_opened_at


def test_mark_opened_returns_404_when_audit_belongs_to_another_user(
    client, auth_headers, test_engine
):
    other_user = uuid4()
    with Session(test_engine) as session:
        log = _seed_audit(
            session, other_user, action="notification.reservation_event.booking_confirmed.push_dispatched"
        )
        audit_id = log.id

    response = client.post(
        f"/api/v1/me/notifications/{audit_id}/opened", headers=auth_headers
    )
    assert response.status_code == 404
