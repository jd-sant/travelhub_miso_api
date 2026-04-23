from abc import ABC, abstractmethod
from uuid import UUID

from domain.schemas.reservation import (
    ReservationEventCreateRequest,
    ReservationEventResponse,
)


class ReservationEventRepository(ABC):
    @abstractmethod
    def add(self, payload: ReservationEventCreateRequest) -> ReservationEventResponse:
        pass

    @abstractmethod
    def list_by_reservation(self, reservation_id: UUID) -> list[ReservationEventResponse]:
        pass
