from uuid import UUID

from domain.ports.reservation_event_repository import ReservationEventRepository
from domain.ports.reservation_repository import ReservationRepository
from domain.schemas.reservation import ReservationHistoryResponse
from errors import ReservationNotFoundError, ReservationOwnershipError


class GetReservationHistoryUseCase:
    def __init__(
        self,
        reservation_repository: ReservationRepository,
        event_repository: ReservationEventRepository,
    ):
        self.reservation_repository = reservation_repository
        self.event_repository = event_repository

    def execute(
        self,
        reservation_id: UUID,
        *,
        actor_user_id: UUID,
    ) -> ReservationHistoryResponse:
        reservation = self.reservation_repository.get_by_id(reservation_id)
        if not reservation:
            raise ReservationNotFoundError("Reservation not found")
        if reservation.id_traveler != actor_user_id:
            raise ReservationOwnershipError("Reservation does not belong to traveler")

        events = self.event_repository.list_by_reservation(reservation_id)
        return ReservationHistoryResponse(reservation_id=reservation_id, events=events)
