from datetime import UTC, datetime
from uuid import UUID, uuid4

from domain.ports.reservation_repository import ReservationRepository
from domain.schemas.reservation import (
    HotelReservationActionResponse,
    ReservationCancellationReason,
    ReservationChangeRecord,
    ReservationStatus,
)
from domain.use_cases.base import BaseUseCase
from errors import ReservationNotFoundError, ReservationStateConflictError

MAX_CANCELLATION_REASON_LENGTH = 500


def _build_cancellation_reason(
    reason: ReservationCancellationReason,
    note: str | None,
) -> str:
    normalized_reason = reason.value
    if note and reason == ReservationCancellationReason.other:
        normalized_reason = f"{normalized_reason}: {note.strip()}"
    return normalized_reason[:MAX_CANCELLATION_REASON_LENGTH].strip()


class CancelHotelReservationUseCase(
    BaseUseCase[
        tuple[UUID, UUID | None, str | None, ReservationCancellationReason, str | None],
        HotelReservationActionResponse,
    ]
):
    def __init__(self, repository: ReservationRepository):
        self.repository = repository

    def execute(
        self,
        reservation_id: UUID,
        *,
        actor_user_id: UUID | None,
        source_ip: str | None,
        reason: ReservationCancellationReason,
        note: str | None = None,
    ) -> HotelReservationActionResponse:
        reservation = self.repository.get_by_id(reservation_id)
        if reservation is None:
            raise ReservationNotFoundError("Reservation not found")

        if reservation.status == ReservationStatus.cancelled.value:
            raise ReservationStateConflictError(
                "No se puede cancelar una reserva cancelada."
            )
        if reservation.status == ReservationStatus.completed.value:
            raise ReservationStateConflictError(
                "No se puede cancelar una reserva completada."
            )

        updated = self.repository.update_status(
            reservation_id, ReservationStatus.cancelled.value
        )
        if updated is None:
            raise ReservationNotFoundError("Reservation not found")

        normalized_reason = _build_cancellation_reason(reason, note)

        self.repository.add_change(
            ReservationChangeRecord(
                id=uuid4(),
                reservation_id=reservation_id,
                action="hotel.cancel",
                previous_status=reservation.status,
                new_status=updated.status,
                reason=normalized_reason,
                actor_user_id=actor_user_id,
                source_ip=source_ip,
                created_at=datetime.now(UTC),
            )
        )

        refund_requested = reservation.status == ReservationStatus.confirmed.value
        return HotelReservationActionResponse(
            reservation=updated,
            status_before=reservation.status,
            status_after=updated.status,
            action_applied="cancelled",
            reason=normalized_reason,
            refund_requested=refund_requested,
        )
