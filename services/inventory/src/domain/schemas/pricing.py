from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


DiscountType = Literal["percentage", "fixed"]


class PricingTargetOption(BaseModel):
    property_id: UUID
    property_name: str
    room_type_id: UUID
    room_type_name: str
    rate_plan_id: UUID
    rate_plan_name: str
    currency: str
    base_price: Decimal


class PricingPreviewRequest(BaseModel):
    property_id: UUID
    rate_plan_id: UUID
    start_date: date
    end_date: date
    proposed_base_price: Decimal | None = Field(default=None, ge=0)
    discount_type: DiscountType | None = None
    discount_value: Decimal | None = Field(default=None, ge=0)
    rule_name: str | None = Field(default=None, max_length=120)


class PricingPreviewResponse(BaseModel):
    property_id: UUID
    property_name: str
    room_type_id: UUID
    room_type_name: str
    rate_plan_id: UUID
    rate_plan_name: str
    currency: str
    start_date: date
    end_date: date
    days_affected: int
    current_base_price: Decimal
    proposed_base_price: Decimal
    discount_type: DiscountType | None = None
    discount_value: Decimal | None = None
    final_price: Decimal
    projected_revenue_before: Decimal
    projected_revenue_after: Decimal
    projected_revenue_delta: Decimal
    sellable_units: int
    requires_confirmation: bool
    impact_summary: str


class PricingApplyRequest(PricingPreviewRequest):
    confirmation_acknowledged: bool = False
    device_label: str | None = Field(default=None, max_length=120)
    device_platform: str | None = Field(default=None, max_length=80)


class PricingHistoryItem(BaseModel):
    id: UUID
    property_id: UUID
    property_name: str
    room_type_name: str
    rate_plan_name: str
    currency: str
    rule_name: str | None = None
    start_date: date
    end_date: date
    previous_base_price: Decimal
    new_base_price: Decimal
    discount_type: DiscountType | None = None
    discount_value: Decimal | None = None
    final_price: Decimal
    projected_revenue_before: Decimal
    projected_revenue_after: Decimal
    actor_user_id: UUID
    actor_email: str
    actor_ip: str | None = None
    device_label: str | None = None
    device_platform: str | None = None
    request_checksum: str | None = None
    created_at: datetime
    reverted_at: datetime | None = None
    can_revert: bool = True


class PricingApplyResponse(BaseModel):
    preview: PricingPreviewResponse
    history_entry: PricingHistoryItem


class PricingRevertResponse(BaseModel):
    reverted_change_id: UUID
    reverted_at: datetime
