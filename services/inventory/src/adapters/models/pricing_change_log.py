from datetime import UTC, date, datetime
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel


class PricingChangeLog(SQLModel, table=True):
    __tablename__ = "pricing_change_log"

    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    property_id: UUID = Field(index=True)
    property_name: str = Field(max_length=160)
    room_type_id: UUID = Field(index=True)
    room_type_name: str = Field(max_length=140)
    rate_plan_id: UUID = Field(index=True)
    rate_plan_name: str = Field(max_length=140)
    currency: str = Field(max_length=12)
    rule_name: str | None = Field(default=None, max_length=120)
    start_date: date = Field(index=True)
    end_date: date = Field(index=True)
    previous_base_price: str
    new_base_price: str
    discount_type: str | None = Field(default=None, max_length=20)
    discount_value: str | None = None
    final_price: str
    projected_revenue_before: str
    projected_revenue_after: str
    actor_user_id: UUID = Field(index=True)
    actor_email: str = Field(max_length=160)
    actor_ip: str | None = Field(default=None, max_length=120)
    device_label: str | None = Field(default=None, max_length=120)
    device_platform: str | None = Field(default=None, max_length=80)
    request_checksum: str | None = Field(default=None, max_length=64)
    previous_calendar_snapshot: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    reverted_at: datetime | None = None
