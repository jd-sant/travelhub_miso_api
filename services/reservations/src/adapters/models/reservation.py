from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel


class Reservation(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    id_traveler: UUID = Field(index=True)
    id_property: UUID = Field(index=True)
    id_room: UUID = Field(index=True)
    check_in_date: datetime = Field(index=True)
    check_out_date: datetime = Field(index=True)
    number_of_guests: int = Field(ge=1)
    total_price: Decimal = Field(decimal_places=2, max_digits=10)
    currency: str = Field(max_length=3)
    status: str = Field(default="pending_payment")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
