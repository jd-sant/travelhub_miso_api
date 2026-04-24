from abc import ABC, abstractmethod
from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from domain.schemas.reservation import (
    HotelReservationListItem,
    ReservationChangeRecord,
    ReservationCreateRequest,
    ReservationResponse,
)


class ReservationRepository(ABC):
    @abstractmethod
    def add(
        self,
        payload: ReservationCreateRequest,
        total_price: Decimal,
        reservation_id: UUID | None = None,
    ) -> ReservationResponse:
        pass

    @abstractmethod
    def get_by_id(self, id: UUID) -> Optional[ReservationResponse]:
        pass

    @abstractmethod
    def list_by_traveler(self, id_traveler: UUID) -> list[ReservationResponse]:
        pass

    @abstractmethod
    def list_by_property(
        self,
        id_property: UUID,
        *,
        status: str | None = None,
    ) -> list[HotelReservationListItem]:
        pass

    @abstractmethod
    def check_room_availability(
        self, id_room: UUID, check_in: datetime, check_out: datetime
    ) -> bool:
        pass

    @abstractmethod
    def update_status(self, id: UUID, status: str) -> Optional[ReservationResponse]:
        pass

    @abstractmethod
    def add_change(self, payload: ReservationChangeRecord) -> ReservationChangeRecord:
        pass
