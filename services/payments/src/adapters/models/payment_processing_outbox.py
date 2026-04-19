from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


class PaymentProcessingOutbox(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint("payment_id", name="uq_payment_processing_outbox_payment_id"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    payment_id: UUID = Field(foreign_key="payment.id", index=True)
    checkout_session_id: UUID = Field(index=True)
    status: str = Field(default="pending", index=True)
    attempt_count: int = Field(default=0)
    max_attempts: int = Field(default=5)
    next_retry_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        index=True,
    )
    source_ip: str | None = Field(default=None, max_length=64)
    last_error: str | None = None
    last_attempt_at: datetime | None = None
    processed_at: datetime | None = None
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        index=True,
    )
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
