from abc import ABC, abstractmethod
from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from domain.schemas.reservation import (
    HotelReservationListItem,
    InternalNoteResponse,
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
    def list_by_traveler(
        self,
        id_traveler: UUID,
        status_group: str | None = None,
    ) -> list[ReservationResponse]:
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
        self,
        id_room: UUID,
        check_in: datetime,
        check_out: datetime,
        exclude_reservation_id: UUID | None = None,
    ) -> bool:
        pass

    @abstractmethod
    def check_properties_availability(
        self,
        property_ids: list[UUID],
        check_in: datetime,
        check_out: datetime,
    ) -> tuple[list[UUID], list[UUID]]:
        """Return (available_ids, blocked_ids) for the given range.

        A property is blocked if any of its reservations is not in a cancelled-like
        status and overlaps [check_in, check_out).
        """
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

    @abstractmethod
    def list_by_properties(
        self,
        property_ids: list[UUID],
        *,
        statuses: list[str] | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        guest_ids: list[UUID] | None = None,
        sort_by: str = "check_in_date",
        sort_dir: str = "desc",
        page: int = 1,
        page_size: int = 10,
    ) -> tuple[list[ReservationResponse], int]:
        pass

    @abstractmethod
    def list_confirmed_ids_by_properties(
        self,
        property_ids: list[UUID],
        *,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[UUID]:
        pass

    @abstractmethod
    def list_confirmed_with_check_in_by_properties(
        self,
        property_ids: list[UUID],
        *,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[tuple[UUID, datetime]]:
        pass

    @abstractmethod
    def list_confirmed_revenue_rows_by_properties(
        self,
        property_ids: list[UUID],
        *,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[tuple[UUID, datetime, Decimal, str]]:
        pass

    @abstractmethod
    def operational_metrics_for_properties(
        self,
        property_ids: list[UUID],
        *,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> dict:
        pass

    @abstractmethod
    def add_change(self, payload: ReservationChangeRecord) -> ReservationChangeRecord:
        pass

    @abstractmethod
    def list_changes(self, reservation_id: UUID) -> list[ReservationChangeRecord]:
        pass

    @abstractmethod
    def add_note(
        self,
        reservation_id: UUID,
        content: str,
        author_user_id: UUID,
        author_name: str | None,
    ) -> InternalNoteResponse:
        pass

    @abstractmethod
    def list_notes(self, reservation_id: UUID) -> list[InternalNoteResponse]:
        pass
