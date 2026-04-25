from datetime import datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field


class ReservationStatus(str, Enum):
    pending_payment = "pending_payment"
    confirmed = "confirmed"
    cancelled = "cancelled"


class ReservationCreateRequest(BaseModel):
    id_traveler: UUID
    id_property: UUID
    id_room: UUID
    check_in_date: datetime
    check_out_date: datetime
    number_of_guests: int = Field(ge=1)
    currency: str = Field(max_length=3)


class ReservationStatusUpdateRequest(BaseModel):
    status: ReservationStatus


class ReservationResponse(BaseModel):
    id: UUID
    id_traveler: UUID
    id_property: UUID
    id_room: UUID
    check_in_date: datetime
    check_out_date: datetime
    number_of_guests: int
    total_price: Decimal
    currency: str
    status: str
    hold_expires_at: datetime
    created_at: datetime
    updated_at: datetime


class ReservationSummary(BaseModel):
    id: UUID
    status: str
    total_price: Decimal
    currency: str
    check_in_date: datetime
    check_out_date: datetime
    hold_expires_at: datetime
    created_at: datetime


class ReservationCheckStatusResponse(BaseModel):
    reservation: ReservationResponse
    status_before: str
    status_after: str
    action_applied: str


class HostReservationItem(BaseModel):
    id: UUID
    reservation_number: str
    id_property: UUID
    id_room: UUID
    id_traveler: UUID
    guest_full_name: str | None = None
    room_type: str | None = None
    check_in_date: datetime
    check_out_date: datetime
    number_of_guests: int
    total_price: Decimal
    currency: str
    status: str
    created_at: datetime


class HostReservationsPage(BaseModel):
    items: list[HostReservationItem]
    total: int
    page: int
    page_size: int


class HostMetrics(BaseModel):
    active_reservations: int
    occupancy_rate: float
    revenue_amount: Decimal
    revenue_currency: str | None = None
    average_daily_rate: Decimal
    total_nights: int


class HostRevenueBucket(BaseModel):
    bucket: datetime
    revenue: Decimal
    reservations: int


class HostRevenueTrends(BaseModel):
    granularity: str
    currency: str | None = None
    buckets: list[HostRevenueBucket]

