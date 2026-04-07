from abc import ABC, abstractmethod
from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from domain.schemas.reservation import ReservationCreateRequest, ReservationResponse


class ReservationRepository(ABC):
    @abstractmethod
    def add(self, payload: ReservationCreateRequest, total_price: Decimal) -> ReservationResponse:
        pass

    @abstractmethod
    def get_by_id(self, id: UUID) -> Optional[ReservationResponse]:
        pass

    @abstractmethod
    def list_by_traveler(self, id_traveler: UUID) -> list[ReservationResponse]:
        pass

    @abstractmethod
    def check_room_availability(
        self, id_room: UUID, check_in: datetime, check_out: datetime
    ) -> bool:
        pass

    @abstractmethod
    def update_status(self, id: UUID, status: str) -> Optional[ReservationResponse]:
        pass
