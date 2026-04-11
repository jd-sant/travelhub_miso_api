from uuid import UUID

from domain.use_cases.update_reservation import UpdateReservationStatusUseCase
from domain.schemas.reservation import ReservationCheckStatusResponse
from domain.use_cases.base import BaseUseCase
from errors import ReservationNotFoundError


class CheckReservationStatusUseCase(BaseUseCase[UUID, ReservationCheckStatusResponse]):
    def __init__(self, updater: UpdateReservationStatusUseCase):
        self.updater = updater

    def execute(self, reservation_id: UUID) -> ReservationCheckStatusResponse:
        reservation = self.updater.repository.get_by_id(reservation_id)
        if not reservation:
            raise ReservationNotFoundError("Reservation not found")

        status_before = reservation.status
        action_applied = "none"

        if status_before == "pending_payment":
            result = self.updater.execute(reservation_id, "cancelled")
            reservation = result.reservation
            action_applied = "cancelled"

        return ReservationCheckStatusResponse(
            reservation=reservation,
            status_before=status_before,
            status_after=reservation.status,
            action_applied=action_applied,
        )