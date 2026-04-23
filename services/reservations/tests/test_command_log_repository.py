from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from domain.schemas.reservation import ReservationCommandType, ReservationCreateRequest


class TestReservationCommandLogRepository:
    def test_add_and_get_by_idempotency(
        self, reservation_repository, reservation_command_log_repository
    ):
        check_in = datetime.now(UTC) + timedelta(days=5)
        check_out = check_in + timedelta(days=2)
        reservation = reservation_repository.add(
            ReservationCreateRequest(
                id_traveler=uuid4(),
                id_property=uuid4(),
                id_room=uuid4(),
                check_in_date=check_in,
                check_out_date=check_out,
                number_of_guests=2,
                currency="USD",
            ),
            Decimal("216.00"),
        )

        payload = {
            "reservation": {
                "id": str(reservation.id),
                "status": "modification_pending_payment",
            },
            "idempotency_key": "idem-123",
        }
        reservation_command_log_repository.add(
            reservation.id,
            ReservationCommandType.modification_confirm,
            "idem-123",
            payload,
        )

        recovered = reservation_command_log_repository.get_by_idempotency(
            reservation.id,
            ReservationCommandType.modification_confirm,
            "idem-123",
        )

        assert recovered == payload
