from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, field_serializer


class PropertyAvailabilityQuery(BaseModel):
    property_id: UUID
    check_in: date
    check_out: date
    guests: int = Field(ge=1)


class PropertyAvailabilityResponse(BaseModel):
    property_id: UUID
    check_in: date
    check_out: date
    guests: int = Field(ge=1)
    available: bool
    price_from: Decimal | None = None
    currency: str | None = None

    @field_serializer("price_from")
    def serialize_price_from(self, value: Decimal | None) -> float | None:
        return float(value) if value is not None else None
