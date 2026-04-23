from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from domain.schemas.reservation import CancellationPolicyType


class PropertyDetailResponse(BaseModel):
    id: UUID
    max_guests: int = Field(ge=0)
    name: str = ""
    cover_image_url: str | None = None


class PropertyCancellationPolicyResponse(BaseModel):
    property_id: UUID
    policy_type: CancellationPolicyType
    minimum_notice_hours: int = Field(ge=0)
    penalty_percentage: Decimal = Field(ge=0, le=100)
    timezone: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
