from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class ReservationCreateRequest(BaseModel):
    id_traveler: UUID
    id_property: UUID
    id_room: UUID
    check_in_date: datetime
    check_out_date: datetime
    number_of_guests: int = Field(ge=1)
    currency: str = Field(max_length=3)


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
    created_at: datetime
    updated_at: datetime


class ReservationSummary(BaseModel):
    id: UUID
    status: str
    total_price: Decimal
    currency: str
    check_in_date: datetime
    check_out_date: datetime
    created_at: datetime

