from uuid import UUID

from domain.ports.reservation_repository import ReservationRepository
from domain.schemas.reservation import (
    ReservationCheckStatusResponse,
    ReservationResponse,
)
from domain.use_cases.base import BaseUseCase
from errors import ReservationNotFoundError


class UpdateReservationStatusUseCase(BaseUseCase[UUID, ReservationCheckStatusResponse]):
    def __init__(self, repository: ReservationRepository):
        self.repository = repository

    def execute(self, reservation_id: UUID, status: str) -> ReservationCheckStatusResponse:
        reservation = self.repository.get_by_id(reservation_id)
        if not reservation:
            raise ReservationNotFoundError("Reservation not found")

        status_before = reservation.status
        updated_reservation = self.repository.update_status(reservation_id, status)
        if not updated_reservation:
            raise ReservationNotFoundError("Reservation not found")

        return ReservationCheckStatusResponse(
            reservation=updated_reservation,
            status_before=status_before,
            status_after=updated_reservation.status,
            action_applied=status,
        )