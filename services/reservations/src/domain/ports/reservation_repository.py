from abc import ABC, abstractmethod
from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from domain.schemas.reservation import ReservationCreateRequest, ReservationResponse


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
    def check_room_availability(
        self,
        id_room: UUID,
        check_in: datetime,
        check_out: datetime,
        exclude_reservation_id: UUID | None = None,
    ) -> bool:
        pass

    @abstractmethod
    def update_status(
        self,
        id: UUID,
        status: str,
        *,
        expected_version: int | None = None,
    ) -> Optional[ReservationResponse]:
        pass

    @abstractmethod
    def apply_updates(
        self,
        id: UUID,
        *,
        status: str,
        expected_version: int | None = None,
        check_in_date: datetime | None = None,
        check_out_date: datetime | None = None,
        number_of_guests: int | None = None,
        total_price: Decimal | None = None,
        last_policy_snapshot: str | None = None,
        cancelled_at: datetime | None = None,
        cancellation_reason: str | None = None,
    ) -> Optional[ReservationResponse]:
        pass
