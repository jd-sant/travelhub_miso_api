from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

import pytest

from adapters.models.reservation import Reservation
from domain.schemas.property_service import (
    PropertyCancellationPolicyResponse,
    PropertyDetailResponse,
)
from domain.schemas.reservation import (
    CancellationPolicyType,
    ReservationCreateRequest,
    ReservationModificationPreviewRequest,
)
from domain.use_cases.preview_reservation_cancellation import (
    PreviewReservationCancellationUseCase,
)
from domain.use_cases.preview_reservation_modification import (
    PreviewReservationModificationUseCase,
)


class FakePropertyServiceClient:
    def __init__(
        self,
        *,
        max_guests: int = 12,
        policy_type: CancellationPolicyType = CancellationPolicyType.full_refund,
        minimum_notice_hours: int = 24,
        penalty_percentage: Decimal = Decimal("0.00"),
    ):
        self.max_guests = max_guests
        self.policy_type = policy_type
        self.minimum_notice_hours = minimum_notice_hours
        self.penalty_percentage = penalty_percentage

    def get_property(self, property_id: UUID) -> PropertyDetailResponse:
        return PropertyDetailResponse(id=property_id, max_guests=self.max_guests)

    def get_cancellation_policy(
        self, property_id: UUID
    ) -> PropertyCancellationPolicyResponse:
        now = datetime.now(UTC)
        return PropertyCancellationPolicyResponse(
            property_id=property_id,
            policy_type=self.policy_type,
            minimum_notice_hours=self.minimum_notice_hours,
            penalty_percentage=self.penalty_percentage,
            timezone="UTC",
            is_active=True,
            created_at=now,
            updated_at=now,
        )


def _create_confirmed_reservation(
    reservation_repository,
    *,
    traveler_id,
    property_id,
    room_id,
    check_in: datetime,
    nights: int,
    currency: str = "COP",
):
    check_out = check_in + timedelta(days=nights)
    created = reservation_repository.add(
        ReservationCreateRequest(
            id_traveler=traveler_id,
            id_property=property_id,
            id_room=room_id,
            check_in_date=check_in,
            check_out_date=check_out,
            number_of_guests=2,
            currency=currency,
        ),
        Decimal("238.00") if nights == 2 and currency == "COP" else Decimal("357.00"),
    )
    reservation_repository.update_status(created.id, "confirmed")
    return created, check_in, check_out


class TestPreviewReservationModificationUseCase:
    def test_execute_returns_allowed_preview_and_records_event(
        self, reservation_repository, reservation_event_repository, traveler_id, property_id, room_id
    ):
        check_in = datetime.now(UTC) + timedelta(days=5)
        reservation, _, check_out = _create_confirmed_reservation(
            reservation_repository,
            traveler_id=traveler_id,
            property_id=property_id,
            room_id=room_id,
            check_in=check_in,
            nights=2,
        )
        use_case = PreviewReservationModificationUseCase(
            reservation_repository,
            FakePropertyServiceClient(max_guests=12),
            reservation_event_repository,
        )

        payload = ReservationModificationPreviewRequest(
            check_in_date=check_in + timedelta(days=1),
            check_out_date=check_out + timedelta(days=2),
            number_of_guests=3,
        )

        result = use_case.execute(reservation.id, payload)

        assert result.change_allowed is True
        assert result.requires_additional_charge is True
        assert result.delta_amount == Decimal("119.00")
        assert result.estimated_refund_amount == Decimal("0.00")
        assert result.price_after.total_price == Decimal("357.00")
        assert result.reservation_after_preview.number_of_guests == 3
        assert result.reasons == []

        events = reservation_event_repository.list_by_reservation(reservation.id)
        assert len(events) == 1
        assert events[0].event_type == "modification_previewed"
        assert events[0].result == "success"

    def test_execute_rejects_preview_when_capacity_is_exceeded(
        self, reservation_repository, reservation_event_repository, traveler_id, property_id, room_id
    ):
        check_in = datetime.now(UTC) + timedelta(days=5)
        reservation, _, check_out = _create_confirmed_reservation(
            reservation_repository,
            traveler_id=traveler_id,
            property_id=property_id,
            room_id=room_id,
            check_in=check_in,
            nights=2,
        )
        use_case = PreviewReservationModificationUseCase(
            reservation_repository,
            FakePropertyServiceClient(max_guests=2),
            reservation_event_repository,
        )

        payload = ReservationModificationPreviewRequest(
            check_in_date=check_in + timedelta(days=1),
            check_out_date=check_out + timedelta(days=2),
            number_of_guests=3,
        )

        result = use_case.execute(reservation.id, payload)

        assert result.change_allowed is False
        assert any("capacity" in reason.lower() for reason in result.reasons)


class TestPreviewReservationCancellationUseCase:
    def test_execute_returns_full_refund_preview_and_records_event(
        self, reservation_repository, reservation_event_repository, traveler_id, property_id, room_id
    ):
        check_in = datetime.now(UTC) + timedelta(days=5)
        reservation, _, _ = _create_confirmed_reservation(
            reservation_repository,
            traveler_id=traveler_id,
            property_id=property_id,
            room_id=room_id,
            check_in=check_in,
            nights=2,
        )
        use_case = PreviewReservationCancellationUseCase(
            reservation_repository,
            FakePropertyServiceClient(
                policy_type=CancellationPolicyType.full_refund,
                minimum_notice_hours=24,
            ),
            reservation_event_repository,
        )

        result = use_case.execute(reservation.id)

        assert result.change_allowed is True
        assert result.refund_type == CancellationPolicyType.full_refund
        assert result.refund_amount == Decimal("238.00")
        assert result.penalty_amount == Decimal("0.00")
        assert result.reasons == []

        events = reservation_event_repository.list_by_reservation(reservation.id)
        assert len(events) == 1
        assert events[0].event_type == "cancellation_previewed"
        assert events[0].result == "success"

    def test_execute_rejects_preview_when_window_expired(
        self, reservation_repository, reservation_event_repository, traveler_id, property_id, room_id
    ):
        check_in = datetime.now(UTC) + timedelta(hours=1)
        reservation, _, _ = _create_confirmed_reservation(
            reservation_repository,
            traveler_id=traveler_id,
            property_id=property_id,
            room_id=room_id,
            check_in=check_in,
            nights=2,
        )
        use_case = PreviewReservationCancellationUseCase(
            reservation_repository,
            FakePropertyServiceClient(
                policy_type=CancellationPolicyType.partial_refund,
                minimum_notice_hours=48,
                penalty_percentage=Decimal("25.00"),
            ),
            reservation_event_repository,
        )

        result = use_case.execute(reservation.id)

        assert result.change_allowed is False
        assert result.refund_amount == Decimal("0.00")
        assert result.penalty_amount == Decimal("238.00")
        assert any("window" in reason.lower() for reason in result.reasons)
