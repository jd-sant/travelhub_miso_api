from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from domain.schemas.reservation import CancellationPolicyType


class PropertyDetailResponse(BaseModel):
    id: UUID
    max_guests: int = Field(ge=0)
    price_per_night: Decimal
    name: str | None = None
    cover_image_url: str | None = None
    cleaning_fee: Decimal = Decimal("0")
    tax_rate: Decimal = Decimal("0")


class PropertyCancellationPolicyResponse(BaseModel):
    property_id: UUID
    policy_type: CancellationPolicyType
    minimum_notice_hours: int = Field(ge=0)
    penalty_percentage: Decimal = Field(ge=0, le=100)
    timezone: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
