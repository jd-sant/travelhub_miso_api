from datetime import UTC, datetime
from uuid import UUID

from domain.ports.reservation_event_repository import ReservationEventRepository
from domain.ports.reservation_repository import ReservationRepository
from domain.schemas.reservation import (
    ReservationCheckStatusResponse,
    ReservationEventCreateRequest,
    ReservationEventResult,
    ReservationEventType,
    ReservationRefundResultRequest,
)
from errors import (
    InvalidReservationStatusError,
    ReservationNotFoundError,
)


class ApplyRefundResultUseCase:
    def __init__(
        self,
        reservation_repository: ReservationRepository,
        event_repository: ReservationEventRepository,
    ):
        self.reservation_repository = reservation_repository
        self.event_repository = event_repository

    @staticmethod
    def _resolve_status_transition(current_status: str, callback_status: str) -> tuple[str, str]:
        if callback_status == "succeeded":
            if current_status == "cancel_requested":
                return "cancelled", "refund_completed"
            if current_status == "refund_pending":
                return "modification_confirmed", "modification_refund_completed"
            raise InvalidReservationStatusError(
                "Current reservation status does not accept refund success callback"
            )
        return "refund_failed", "refund_failed"

    def execute(
        self,
        reservation_id: UUID,
        payload: ReservationRefundResultRequest,
        *,
        correlation_id: str | None = None,
    ) -> ReservationCheckStatusResponse:
        reservation_before = self.reservation_repository.get_by_id(reservation_id)
        if not reservation_before:
            raise ReservationNotFoundError("Reservation not found")

        status_after, action_applied = self._resolve_status_transition(
            reservation_before.status,
            payload.status.value,
        )

        updated = self.reservation_repository.apply_updates(
            reservation_id,
            status=status_after,
            expected_version=reservation_before.version,
            cancelled_at=(
                datetime.now(UTC).replace(tzinfo=None)
                if status_after == "cancelled"
                else None
            ),
        )
        if not updated:
            raise ReservationNotFoundError("Reservation not found")

        self.event_repository.add(
            ReservationEventCreateRequest(
                reservation_id=reservation_id,
                event_type=ReservationEventType.status_changed,
                result=(
                    ReservationEventResult.success
                    if payload.status.value == "succeeded"
                    else ReservationEventResult.failed
                ),
                before_payload=reservation_before.model_dump(mode="json"),
                after_payload={
                    **updated.model_dump(mode="json"),
                    "correlation_id": correlation_id,
                    "callback_type": "refund_result",
                    "callback_status": payload.status.value,
                    "refund_id": str(payload.refund_id) if payload.refund_id else None,
                    "amount_in_cents": payload.amount_in_cents,
                },
            )
        )

        return ReservationCheckStatusResponse(
            reservation=updated,
            status_before=reservation_before.status,
            status_after=updated.status,
            action_applied=action_applied,
        )