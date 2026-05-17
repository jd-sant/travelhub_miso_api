"""Tests for POST /api/v1/internal/reservations/availability-check."""
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlmodel import Session

from adapters.models.reservation import Reservation
from core.config import settings


URL = "/api/v1/internal/reservations/availability-check"


def _api_key_headers() -> dict[str, str]:
    return {"X-Internal-Api-Key": settings.internal_api_key}


def _add_reservation(
    session: Session,
    *,
    property_id,
    check_in: datetime,
    check_out: datetime,
    status: str = "confirmed",
) -> None:
    session.add(
        Reservation(
            id=uuid4(),
            id_traveler=uuid4(),
            id_property=property_id,
            id_room=uuid4(),
            check_in_date=check_in.replace(tzinfo=None),
            check_out_date=check_out.replace(tzinfo=None),
            number_of_guests=2,
            total_price=100,
            currency="USD",
            status=status,
        )
    )
    session.commit()


def test_availability_check_requires_api_key(client: TestClient):
    response = client.post(
        URL,
        json={
            "property_ids": [str(uuid4())],
            "check_in": "2026-06-10",
            "check_out": "2026-06-15",
        },
    )
    assert response.status_code == 403


def test_availability_check_rejects_wrong_api_key(client: TestClient):
    response = client.post(
        URL,
        headers={"X-Internal-Api-Key": "wrong"},
        json={
            "property_ids": [str(uuid4())],
            "check_in": "2026-06-10",
            "check_out": "2026-06-15",
        },
    )
    assert response.status_code == 403


def test_availability_check_with_no_reservations_returns_all_available(
    client: TestClient,
):
    p1, p2, p3 = uuid4(), uuid4(), uuid4()
    response = client.post(
        URL,
        headers=_api_key_headers(),
        json={
            "property_ids": [str(p1), str(p2), str(p3)],
            "check_in": "2026-06-10",
            "check_out": "2026-06-15",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert set(data["available"]) == {str(p1), str(p2), str(p3)}
    assert data["blocked"] == []


def test_availability_check_marks_property_with_overlapping_reservation_as_blocked(
    client: TestClient, session: Session
):
    p_blocked, p_free = uuid4(), uuid4()
    _add_reservation(
        session,
        property_id=p_blocked,
        check_in=datetime(2026, 6, 12, tzinfo=UTC),
        check_out=datetime(2026, 6, 14, tzinfo=UTC),
        status="confirmed",
    )

    response = client.post(
        URL,
        headers=_api_key_headers(),
        json={
            "property_ids": [str(p_blocked), str(p_free)],
            "check_in": "2026-06-10",
            "check_out": "2026-06-15",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["available"] == [str(p_free)]
    assert data["blocked"] == [str(p_blocked)]


def test_availability_check_ignores_cancelled_reservations(
    client: TestClient, session: Session
):
    p = uuid4()
    _add_reservation(
        session,
        property_id=p,
        check_in=datetime(2026, 6, 12, tzinfo=UTC),
        check_out=datetime(2026, 6, 14, tzinfo=UTC),
        status="cancelled",
    )
    response = client.post(
        URL,
        headers=_api_key_headers(),
        json={
            "property_ids": [str(p)],
            "check_in": "2026-06-10",
            "check_out": "2026-06-15",
        },
    )
    assert response.status_code == 200
    assert response.json() == {"available": [str(p)], "blocked": []}


def test_availability_check_treats_pending_payment_as_blocking(
    client: TestClient, session: Session
):
    p = uuid4()
    _add_reservation(
        session,
        property_id=p,
        check_in=datetime(2026, 6, 12, tzinfo=UTC),
        check_out=datetime(2026, 6, 14, tzinfo=UTC),
        status="pending_payment",
    )
    response = client.post(
        URL,
        headers=_api_key_headers(),
        json={
            "property_ids": [str(p)],
            "check_in": "2026-06-10",
            "check_out": "2026-06-15",
        },
    )
    assert response.status_code == 200
    assert response.json() == {"available": [], "blocked": [str(p)]}


def test_availability_check_non_overlapping_reservation_does_not_block(
    client: TestClient, session: Session
):
    p = uuid4()
    # Reservation totally before the requested window
    _add_reservation(
        session,
        property_id=p,
        check_in=datetime(2026, 5, 1, tzinfo=UTC),
        check_out=datetime(2026, 5, 5, tzinfo=UTC),
        status="confirmed",
    )
    response = client.post(
        URL,
        headers=_api_key_headers(),
        json={
            "property_ids": [str(p)],
            "check_in": "2026-06-10",
            "check_out": "2026-06-15",
        },
    )
    assert response.status_code == 200
    assert response.json() == {"available": [str(p)], "blocked": []}


def test_availability_check_partial_overlap_blocks(
    client: TestClient, session: Session
):
    p = uuid4()
    # Reservation extending into the start of the window
    _add_reservation(
        session,
        property_id=p,
        check_in=datetime(2026, 6, 8, tzinfo=UTC),
        check_out=datetime(2026, 6, 11, tzinfo=UTC),
        status="confirmed",
    )
    response = client.post(
        URL,
        headers=_api_key_headers(),
        json={
            "property_ids": [str(p)],
            "check_in": "2026-06-10",
            "check_out": "2026-06-15",
        },
    )
    assert response.json() == {"available": [], "blocked": [str(p)]}


def test_availability_check_invalid_dates_returns_400(client: TestClient):
    p = uuid4()
    response = client.post(
        URL,
        headers=_api_key_headers(),
        json={
            "property_ids": [str(p)],
            "check_in": "2026-06-15",
            "check_out": "2026-06-10",
        },
    )
    assert response.status_code == 400


def test_availability_check_empty_property_ids_returns_422(client: TestClient):
    response = client.post(
        URL,
        headers=_api_key_headers(),
        json={
            "property_ids": [],
            "check_in": "2026-06-10",
            "check_out": "2026-06-15",
        },
    )
    assert response.status_code == 422


def test_availability_check_preserves_input_order(
    client: TestClient, session: Session
):
    p1, p2, p3, p4 = uuid4(), uuid4(), uuid4(), uuid4()
    # Block p2 and p4
    for p in (p2, p4):
        _add_reservation(
            session,
            property_id=p,
            check_in=datetime(2026, 6, 12, tzinfo=UTC),
            check_out=datetime(2026, 6, 14, tzinfo=UTC),
            status="confirmed",
        )
    response = client.post(
        URL,
        headers=_api_key_headers(),
        json={
            "property_ids": [str(p1), str(p2), str(p3), str(p4)],
            "check_in": "2026-06-10",
            "check_out": "2026-06-15",
        },
    )
    data = response.json()
    assert data["available"] == [str(p1), str(p3)]
    assert set(data["blocked"]) == {str(p2), str(p4)}
