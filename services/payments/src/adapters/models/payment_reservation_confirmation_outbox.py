from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


class PaymentReservationConfirmationOutbox(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint("payment_id", name="uq_reservation_confirmation_outbox_payment_id"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    payment_id: UUID = Field(foreign_key="payment.id", index=True)
    reservation_id: UUID = Field(index=True)
    status: str = Field(default="pending", index=True)
    attempt_count: int = Field(default=1)
    max_attempts: int = Field(default=5)
    next_retry_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), index=True)
    last_error: str | None = None
    last_attempt_at: datetime | None = None
    processed_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), index=True)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
