import time
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import jwt
import pytest
from sqlmodel import Session

from adapters.models.reservation import Reservation
from adapters.models.reservation_change import ReservationChange
from core.config import settings
from domain.schemas.reservation import compute_available_actions
from entrypoints.api.main import app
from entrypoints.api.routers.hotel_reservations import get_users_client


HOTEL_USER_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
TRAVELER_ID = UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
PROPERTY_ID = UUID("11111111-1111-1111-1111-111111111111")
ROOM_ID = UUID("22222222-2222-2222-2222-222222222222")


def _hotel_token(user_id: UUID = HOTEL_USER_ID) -> str:
    payload = {
        "sub": str(user_id),
        "email": "hotel@example.com",
        "role": "hotel",
        "exp": datetime.now(UTC) + timedelta(hours=1),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def _traveler_token(user_id: UUID = TRAVELER_ID) -> str:
    payload = {
        "sub": str(user_id),
        "email": "traveler@example.com",
        "role": "traveler",
        "exp": datetime.now(UTC) + timedelta(hours=1),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


class FakeUsersClientWithData:
    def list_by_ids(self, ids):
        return [
            {
                "id": str(TRAVELER_ID),
                "full_name": "Juan Viajero",
                "email": "juan@example.com",
                "phone": "+573001234567",
            }
        ]

    def search_by_name(self, query):
        return []


def _seed_reservation(session: Session, status: str = "confirmed") -> Reservation:
    r = Reservation(
        id=uuid4(),
        id_traveler=TRAVELER_ID,
        id_property=PROPERTY_ID,
        id_room=ROOM_ID,
        check_in_date=datetime.now(UTC) + timedelta(days=10),
        check_out_date=datetime.now(UTC) + timedelta(days=13),
        number_of_guests=2,
        total_price=Decimal("900000.00"),
        currency="COP",
        status=status,
        accommodation_in_cents=750000_00,
        cleaning_fee_in_cents=80000_00,
        service_fee_in_cents=60000_00,
        taxes_in_cents=10000_00,
    )
    session.add(r)
    session.commit()
    session.refresh(r)
    return r


def _seed_change(session: Session, reservation_id: UUID) -> ReservationChange:
    c = ReservationChange(
        id=uuid4(),
        reservation_id=reservation_id,
        action="hotel.confirm",
        previous_status="pending_payment",
        new_status="confirmed",
        reason="hotel_confirmation",
        actor_user_id=HOTEL_USER_ID,
    )
    session.add(c)
    session.commit()
    session.refresh(c)
    return c


# ---------------------------------------------------------------------------
# Unit tests — available_actions (pure function, no DB)
# ---------------------------------------------------------------------------

def test_available_actions_pending_payment_has_confirm_and_cancel():
    actions = {a.action for a in compute_available_actions("pending_payment")}
    assert "confirm" in actions
    assert "cancel" in actions


def test_available_actions_confirmed_has_only_cancel():
    actions = {a.action for a in compute_available_actions("confirmed")}
    assert "confirm" not in actions
    assert "cancel" in actions


def test_available_actions_cancelled_is_empty():
    actions = compute_available_actions("cancelled")
    assert actions == []


def test_available_actions_completed_is_empty():
    actions = compute_available_actions("completed")
    assert actions == []


def test_available_actions_modification_confirmed_has_confirm_and_cancel():
    actions = {a.action for a in compute_available_actions("modification_confirmed")}
    assert "confirm" in actions
    assert "cancel" in actions


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------

def test_get_detail_returns_full_response(client, session):
    app.dependency_overrides[get_users_client] = lambda: FakeUsersClientWithData()
    r = _seed_reservation(session)
    resp = client.get(
        f"/api/v1/hotel/reservations/{r.id}",
        headers={"Authorization": f"Bearer {_hotel_token()}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["reservation"]["id"] == str(r.id)
    assert data["reservation"]["status"] == "confirmed"
    assert data["guest"]["full_name"] == "Juan Viajero"
    assert data["guest"]["email"] == "juan@example.com"
    assert data["change_history"] == []
    assert data["internal_notes"] == []
    assert isinstance(data["available_actions"], list)
    # confirmed → only cancel
    action_names = {a["action"] for a in data["available_actions"]}
    assert "cancel" in action_names
    assert "confirm" not in action_names
    app.dependency_overrides.pop(get_users_client, None)


def test_get_detail_not_found_returns_404(client):
    resp = client.get(
        f"/api/v1/hotel/reservations/{uuid4()}",
        headers={"Authorization": f"Bearer {_hotel_token()}"},
    )
    assert resp.status_code == 404


def test_get_detail_requires_hotel_role(client, session):
    r = _seed_reservation(session)
    resp = client.get(
        f"/api/v1/hotel/reservations/{r.id}",
        headers={"Authorization": f"Bearer {_traveler_token()}"},
    )
    assert resp.status_code == 403


def test_get_detail_includes_change_history(client, session):
    app.dependency_overrides[get_users_client] = lambda: FakeUsersClientWithData()
    r = _seed_reservation(session)
    _seed_change(session, r.id)
    resp = client.get(
        f"/api/v1/hotel/reservations/{r.id}",
        headers={"Authorization": f"Bearer {_hotel_token()}"},
    )
    assert resp.status_code == 200
    history = resp.json()["change_history"]
    assert len(history) == 1
    assert history[0]["action"] == "hotel.confirm"
    assert history[0]["previous_status"] == "pending_payment"
    assert history[0]["new_status"] == "confirmed"
    app.dependency_overrides.pop(get_users_client, None)


def test_add_note_creates_note_and_returns_201(client, session):
    r = _seed_reservation(session)
    resp = client.post(
        f"/api/v1/hotel/reservations/{r.id}/notes",
        json={"content": "El huésped solicitó check-in tardío."},
        headers={"Authorization": f"Bearer {_hotel_token()}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["reservation_id"] == str(r.id)
    assert data["content"] == "El huésped solicitó check-in tardío."
    assert data["author_user_id"] == str(HOTEL_USER_ID)
    assert "id" in data
    assert "created_at" in data


def test_add_note_to_nonexistent_reservation_returns_404(client):
    resp = client.post(
        f"/api/v1/hotel/reservations/{uuid4()}/notes",
        json={"content": "Nota de prueba."},
        headers={"Authorization": f"Bearer {_hotel_token()}"},
    )
    assert resp.status_code == 404


def test_get_detail_includes_internal_notes(client, session):
    app.dependency_overrides[get_users_client] = lambda: FakeUsersClientWithData()
    r = _seed_reservation(session)
    # Add a note first
    client.post(
        f"/api/v1/hotel/reservations/{r.id}/notes",
        json={"content": "Nota interna de prueba."},
        headers={"Authorization": f"Bearer {_hotel_token()}"},
    )
    resp = client.get(
        f"/api/v1/hotel/reservations/{r.id}",
        headers={"Authorization": f"Bearer {_hotel_token()}"},
    )
    assert resp.status_code == 200
    notes = resp.json()["internal_notes"]
    assert len(notes) == 1
    assert notes[0]["content"] == "Nota interna de prueba."
    app.dependency_overrides.pop(get_users_client, None)


def test_add_note_requires_hotel_role(client, session):
    r = _seed_reservation(session)
    resp = client.post(
        f"/api/v1/hotel/reservations/{r.id}/notes",
        json={"content": "Intento no autorizado."},
        headers={"Authorization": f"Bearer {_traveler_token()}"},
    )
    assert resp.status_code == 403


def test_add_note_empty_content_returns_422(client, session):
    r = _seed_reservation(session)
    resp = client.post(
        f"/api/v1/hotel/reservations/{r.id}/notes",
        json={"content": ""},
        headers={"Authorization": f"Bearer {_hotel_token()}"},
    )
    assert resp.status_code == 422


def test_get_detail_price_breakdown_present(client, session):
    app.dependency_overrides[get_users_client] = lambda: FakeUsersClientWithData()
    r = _seed_reservation(session)
    resp = client.get(
        f"/api/v1/hotel/reservations/{r.id}",
        headers={"Authorization": f"Bearer {_hotel_token()}"},
    )
    assert resp.status_code == 200
    breakdown = resp.json()["reservation"]["price_breakdown"]
    assert breakdown is not None
    assert breakdown["accommodation_in_cents"] == 750000_00
    assert breakdown["cleaning_fee_in_cents"] == 80000_00
    app.dependency_overrides.pop(get_users_client, None)


@pytest.mark.performance
def test_detail_p95_below_1000ms(client, session):
    app.dependency_overrides[get_users_client] = lambda: FakeUsersClientWithData()
    r = _seed_reservation(session)
    _seed_change(session, r.id)
    token = _hotel_token()
    latencies = []
    for _ in range(50):
        start = time.perf_counter()
        resp = client.get(
            f"/api/v1/hotel/reservations/{r.id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        latencies.append((time.perf_counter() - start) * 1000)
        assert resp.status_code == 200
    latencies.sort()
    p50 = latencies[int(len(latencies) * 0.50)]
    p95 = latencies[int(len(latencies) * 0.95)]
    p99 = latencies[int(len(latencies) * 0.99)]
    print(
        f"\n[PERF] Hotel reservation detail latency over {len(latencies)} requests:\n"
        f"  P50 = {p50:.2f} ms\n"
        f"  P95 = {p95:.2f} ms\n"
        f"  P99 = {p99:.2f} ms\n"
        f"  Min = {latencies[0]:.2f} ms\n"
        f"  Max = {latencies[-1]:.2f} ms"
    )
    assert p95 < 1000, f"P95 latency {p95:.2f}ms exceeds 1000ms threshold"
    app.dependency_overrides.pop(get_users_client, None)
