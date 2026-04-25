from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from domain.schemas.reservation import (
    ReservationCreateRequest,
    ReservationEventCreateRequest,
    ReservationEventResult,
    ReservationEventType,
)


class TestReservationEventRepository:
    def test_add_persists_event(self, reservation_repository, reservation_event_repository):
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

        created = reservation_event_repository.add(
            ReservationEventCreateRequest(
                reservation_id=reservation.id,
                event_type=ReservationEventType.modification_previewed,
                actor_user_id=reservation.id_traveler,
                source_ip="203.0.113.9",
                result=ReservationEventResult.success,
                before_payload={"number_of_guests": 2},
                after_payload={"number_of_guests": 3},
            )
        )

        assert created.id is not None
        assert created.reservation_id == reservation.id
        assert created.event_type == ReservationEventType.modification_previewed
        assert created.source_ip == "203.0.113.9"
        assert created.before_payload == {"number_of_guests": 2}
        assert created.after_payload == {"number_of_guests": 3}

    def test_list_by_reservation_returns_ordered_events(
        self, reservation_repository, reservation_event_repository
    ):
        check_in = datetime.now(UTC) + timedelta(days=8)
        check_out = check_in + timedelta(days=3)
        reservation = reservation_repository.add(
            ReservationCreateRequest(
                id_traveler=uuid4(),
                id_property=uuid4(),
                id_room=uuid4(),
                check_in_date=check_in,
                check_out_date=check_out,
                number_of_guests=1,
                currency="COP",
            ),
            Decimal("357.00"),
        )

        reservation_event_repository.add(
            ReservationEventCreateRequest(
                reservation_id=reservation.id,
                event_type=ReservationEventType.cancellation_previewed,
                result=ReservationEventResult.success,
            )
        )
        reservation_event_repository.add(
            ReservationEventCreateRequest(
                reservation_id=reservation.id,
                event_type=ReservationEventType.status_changed,
                result=ReservationEventResult.success,
            )
        )

        items = reservation_event_repository.list_by_reservation(reservation.id)

        assert len(items) == 2
        assert items[0].event_type == ReservationEventType.cancellation_previewed
        assert items[1].event_type == ReservationEventType.status_changed
