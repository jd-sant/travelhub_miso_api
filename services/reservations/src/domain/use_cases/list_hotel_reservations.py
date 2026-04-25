from uuid import UUID

from domain.ports.reservation_repository import ReservationRepository
from domain.schemas.reservation import HotelReservationListItem
from domain.use_cases.base import BaseUseCase


class ListHotelReservationsUseCase(
    BaseUseCase[tuple[UUID, str | None], list[HotelReservationListItem]]
):
    def __init__(self, repository: ReservationRepository):
        self.repository = repository

    def execute(
        self,
        property_id: UUID,
        *,
        status: str | None = None,
    ) -> list[HotelReservationListItem]:
        return self.repository.list_by_property(property_id, status=status)
