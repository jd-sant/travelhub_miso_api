from datetime import datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field, field_serializer


class CancellationPolicyType(str, Enum):
    non_refundable = "non_refundable"
    partial_refund = "partial_refund"
    full_refund = "full_refund"


class PropertyCancellationPolicyResponse(BaseModel):
    property_id: UUID
    policy_type: CancellationPolicyType
    minimum_notice_hours: int = Field(ge=0)
    penalty_percentage: Decimal = Field(ge=0, le=100)
    timezone: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    @field_serializer("penalty_percentage")
    def serialize_penalty_percentage(self, value: Decimal) -> float:
        return float(value)
