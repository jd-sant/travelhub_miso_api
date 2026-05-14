"""Tests del endpoint POST /api/v1/internal/reservations/{id}/fire-arrival-reminder."""
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from core.config import settings
from domain.schemas.reservation import ReservationCreateRequest
from domain.use_cases.create_reservation import CreateReservationUseCase


@pytest.fixture
def created_reservation(reservation_repository, traveler_id, property_id, room_id):
    use_case = CreateReservationUseCase(reservation_repository, scheduler=None)
    payload = ReservationCreateRequest(
        id_traveler=traveler_id,
        id_property=property_id,
        id_room=room_id,
        check_in_date=datetime.now(UTC) + timedelta(days=2),
        check_out_date=datetime.now(UTC) + timedelta(days=4),
        number_of_guests=2,
        currency="COP",
    )
    return use_case.execute(payload)


def test_fire_arrival_reminder_requires_internal_api_key(client, created_reservation):
    response = client.post(
        f"/api/v1/internal/reservations/{created_reservation.id}/fire-arrival-reminder"
    )
    assert response.status_code == 403


def test_fire_arrival_reminder_returns_404_for_unknown_reservation(client):
    response = client.post(
        f"/api/v1/internal/reservations/{uuid4()}/fire-arrival-reminder",
        headers={"X-Internal-Api-Key": settings.internal_api_key},
    )
    assert response.status_code == 404


def test_fire_arrival_reminder_returns_400_for_invalid_uuid(client):
    response = client.post(
        "/api/v1/internal/reservations/not-a-uuid/fire-arrival-reminder",
        headers={"X-Internal-Api-Key": settings.internal_api_key},
    )
    assert response.status_code == 400


def test_fire_arrival_reminder_skips_when_notifications_url_not_configured(
    client, created_reservation, monkeypatch
):
    monkeypatch.setenv("NOTIFICATIONS_SERVICE_URL", "")
    response = client.post(
        f"/api/v1/internal/reservations/{created_reservation.id}/fire-arrival-reminder",
        headers={"X-Internal-Api-Key": settings.internal_api_key},
    )
    assert response.status_code == 200
    body = response.json()
    assert body.get("skipped") is True
    assert "notifications_service_not_configured" in body.get("reason", "")


def test_fire_arrival_reminder_dispatches_to_notifications_service(
    client, created_reservation, monkeypatch
):
    monkeypatch.setenv("NOTIFICATIONS_SERVICE_URL", "http://notifications.test.local")

    fake_response = MagicMock()
    fake_response.raise_for_status = MagicMock()

    with patch(
        "entrypoints.api.routers.internal.httpx.post", return_value=fake_response
    ) as mock_post:
        response = client.post(
            f"/api/v1/internal/reservations/{created_reservation.id}/fire-arrival-reminder",
            headers={"X-Internal-Api-Key": settings.internal_api_key},
        )

    assert response.status_code == 200
    assert response.json().get("dispatched") is True

    mock_post.assert_called_once()
    call_kwargs = mock_post.call_args.kwargs
    assert call_kwargs["headers"]["X-Internal-Api-Key"] == settings.internal_api_key
    assert call_kwargs["json"]["event_type"] == "arrival_reminder"
    assert call_kwargs["json"]["reservation_id"] == str(created_reservation.id)


def test_fire_arrival_reminder_skips_when_reservation_cancelled(
    client, session, reservation_repository, created_reservation, monkeypatch
):
    monkeypatch.setenv("NOTIFICATIONS_SERVICE_URL", "http://notifications.test.local")
    # Cambiar estado directamente en DB para simular cancelación
    from adapters.models.reservation import Reservation

    row = session.get(Reservation, created_reservation.id)
    row.status = "cancelled"
    session.add(row)
    session.commit()

    with patch("entrypoints.api.routers.internal.httpx.post") as mock_post:
        response = client.post(
            f"/api/v1/internal/reservations/{created_reservation.id}/fire-arrival-reminder",
            headers={"X-Internal-Api-Key": settings.internal_api_key},
        )

    assert response.status_code == 200
    body = response.json()
    assert body.get("skipped") is True
    assert "cancelled" in body.get("reason", "")
    mock_post.assert_not_called()
