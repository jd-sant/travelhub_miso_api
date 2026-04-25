from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel


class PaymentRefund(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    payment_id: UUID = Field(index=True)
    reservation_id: UUID = Field(index=True, unique=True)
    amount_in_cents: int
    currency: str = Field(max_length=3)
    status: str = Field(index=True, max_length=32)
    gateway_refund_id: str | None = Field(default=None, index=True)
    reason: str = Field(max_length=255)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), index=True)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), index=True)
