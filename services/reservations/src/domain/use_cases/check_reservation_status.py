from uuid import UUID

from domain.ports.reservation_repository import ReservationRepository
from domain.schemas.reservation import ReservationCheckStatusResponse
from domain.use_cases.base import BaseUseCase
from errors import ReservationNotFoundError


class CheckReservationStatusUseCase(BaseUseCase[UUID, ReservationCheckStatusResponse]):
    def __init__(self, repository: ReservationRepository):
        self.repository = repository

    def execute(self, reservation_id: UUID) -> ReservationCheckStatusResponse:
        reservation = self.repository.get_by_id(reservation_id)
        if not reservation:
            raise ReservationNotFoundError("Reservation not found")

        status_before = reservation.status
        action_applied = "none"

        if status_before == "pending_payment":
            updated_reservation = self.repository.update_status(reservation_id, "cancelled")
            if not updated_reservation:
                raise ReservationNotFoundError("Reservation not found")
            reservation = updated_reservation
            action_applied = "cancelled"

        return ReservationCheckStatusResponse(
            reservation=reservation,
            status_before=status_before,
            status_after=reservation.status,
            action_applied=action_applied,
        )