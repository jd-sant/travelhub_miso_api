from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


class PaymentRefund(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_payment_refunds_idempotency_key"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    payment_id: UUID = Field(index=True)
    reservation_id: UUID = Field(index=True)
    traveler_id: UUID = Field(index=True)
    amount_in_cents: int
    currency: str = Field(max_length=3)
    reason: str = Field(max_length=255)
    idempotency_key: str = Field(index=True, max_length=255)
    status: str = Field(index=True)
    retry_count: int = 0
    max_attempts: int
    sla_deadline_at: datetime = Field(index=True)
    next_retry_at: datetime = Field(index=True)
    last_error: str | None = None
    processed_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), index=True)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
