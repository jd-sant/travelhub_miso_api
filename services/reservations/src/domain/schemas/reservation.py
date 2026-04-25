from datetime import datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field


class ReservationStatus(str, Enum):
    pending_payment = "pending_payment"
    confirmed = "confirmed"
    cancelled = "cancelled"
    completed = "completed"


class ReservationCancellationReason(str, Enum):
    maintenance = "maintenance"
    overbooking = "overbooking"
    hotel_policy = "hotel_policy"
    other = "other"


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


class HotelReservationListItem(BaseModel):
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


class HotelReservationConfirmationRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=255)


class HotelReservationCancellationRequest(BaseModel):
    reason: ReservationCancellationReason
    note: str | None = Field(default=None, max_length=500)


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


class HotelReservationActionResponse(BaseModel):
    reservation: ReservationResponse
    status_before: str
    status_after: str
    action_applied: str
    reason: str
    refund_requested: bool = False


class ReservationChangeRecord(BaseModel):
    id: UUID
    reservation_id: UUID
    action: str
    previous_status: str
    new_status: str
    reason: str
    actor_user_id: UUID | None = None
    source_ip: str | None = None
    created_at: datetime

