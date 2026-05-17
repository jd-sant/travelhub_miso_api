"""Tests que verifican que CreateReservationUseCase invoca al scheduler para
programar el recordatorio de llegada usando el lead time parametrizable.
"""
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest

from core.config import settings
from domain.ports.reservation_scheduler import ReservationScheduler
from domain.schemas.reservation import ReservationCreateRequest
from domain.use_cases.create_reservation import CreateReservationUseCase


class FakeScheduler(ReservationScheduler):
    def __init__(self):
        self.expiration_calls = []
        self.arrival_calls = []
        self.cancel_expiration_calls = []
        self.cancel_arrival_calls = []
        self.fail_arrival = False

    def schedule_reservation_expiration(self, reservation_id: str) -> str:
        self.expiration_calls.append(reservation_id)
        return f"verify-{reservation_id}"

    def cancel_reservation_expiration(self, reservation_id: str) -> None:
        self.cancel_expiration_calls.append(reservation_id)

    def schedule_arrival_reminder(self, reservation_id, fire_at):
        if self.fail_arrival:
            raise RuntimeError("aws blew up")
        self.arrival_calls.append((reservation_id, fire_at))
        return f"arrival-{reservation_id}"

    def cancel_arrival_reminder(self, reservation_id: str) -> None:
        self.cancel_arrival_calls.append(reservation_id)


@pytest.fixture
def request_payload(traveler_id, property_id, room_id):
    check_in = datetime.now(UTC) + timedelta(days=10)
    return ReservationCreateRequest(
        id_traveler=traveler_id,
        id_property=property_id,
        id_room=room_id,
        check_in_date=check_in,
        check_out_date=check_in + timedelta(days=2),
        number_of_guests=2,
        currency="COP",
    )


def test_create_reservation_calls_schedule_arrival_reminder(
    reservation_repository, request_payload, monkeypatch
):
    monkeypatch.setenv("ARRIVAL_REMINDER_LEAD_MINUTES", "1440")
    scheduler = FakeScheduler()
    use_case = CreateReservationUseCase(reservation_repository, scheduler=scheduler)

    use_case.execute(request_payload)

    assert len(scheduler.arrival_calls) == 1
    reservation_id, fire_at = scheduler.arrival_calls[0]
    assert isinstance(reservation_id, str)
    # use case normaliza fechas a naive UTC; comparamos en naive UTC.
    naive_check_in = request_payload.check_in_date.astimezone(UTC).replace(tzinfo=None)
    expected = naive_check_in - timedelta(minutes=1440)
    assert abs((fire_at - expected).total_seconds()) < 5


def test_arrival_reminder_uses_parametrizable_lead_minutes(
    reservation_repository, request_payload, monkeypatch
):
    """Si ARRIVAL_REMINDER_LEAD_MINUTES=1 (modo prueba), el fire_at debe estar
    a 1 minuto del check_in en vez de 24h."""
    monkeypatch.setenv("ARRIVAL_REMINDER_LEAD_MINUTES", "1")
    scheduler = FakeScheduler()
    use_case = CreateReservationUseCase(reservation_repository, scheduler=scheduler)

    use_case.execute(request_payload)

    _, fire_at = scheduler.arrival_calls[0]
    naive_check_in = request_payload.check_in_date.astimezone(UTC).replace(tzinfo=None)
    expected = naive_check_in - timedelta(minutes=1)
    assert abs((fire_at - expected).total_seconds()) < 5


def test_arrival_reminder_failure_does_not_break_reservation_creation(
    reservation_repository, request_payload, monkeypatch
):
    """Recordar la HU: el recordatorio es best-effort; si AWS falla, la reserva
    debe crearse igual."""
    monkeypatch.setenv("ARRIVAL_REMINDER_LEAD_MINUTES", "1440")
    scheduler = FakeScheduler()
    scheduler.fail_arrival = True
    use_case = CreateReservationUseCase(reservation_repository, scheduler=scheduler)

    response = use_case.execute(request_payload)

    assert response is not None
    assert scheduler.expiration_calls  # la expiración sí se programó
