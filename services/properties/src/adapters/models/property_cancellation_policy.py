from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel


class PropertyCancellationPolicy(SQLModel, table=True):
    __tablename__ = "property_cancellation_policies"

    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    property_id: UUID = Field(foreign_key="properties.id", index=True, unique=True)
    policy_type: str = Field(max_length=32, index=True)
    minimum_notice_hours: int = Field(default=24, ge=0)
    penalty_percentage: Decimal = Field(default=Decimal("0.00"), decimal_places=2, max_digits=5)
    timezone: str = Field(default="UTC", max_length=64)
    is_active: bool = Field(default=True, index=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
