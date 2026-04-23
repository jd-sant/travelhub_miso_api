from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field


class CancellationPolicyType(str, Enum):
    non_refundable = "non_refundable"
    partial_refund = "partial_refund"
    full_refund = "full_refund"


class PropertyCancellationPolicyResponse(BaseModel):
    property_id: UUID
    policy_type: CancellationPolicyType
    minimum_notice_hours: int = Field(ge=0)
    penalty_percentage: float = Field(ge=0)
    timezone: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
