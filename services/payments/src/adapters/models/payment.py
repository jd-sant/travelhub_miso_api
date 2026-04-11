from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


class Payment(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_payments_idempotency_key"),
        UniqueConstraint("duplicate_guard_key", name="uq_payments_duplicate_guard_key"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    reservation_id: UUID = Field(index=True)
    traveler_id: UUID = Field(index=True)
    provider_code: str = Field(index=True, max_length=64)
    status: str = Field(index=True)
    amount_in_cents: int
    currency: str = Field(max_length=3)
    payment_method_token_hash: str = Field(index=True)
    request_fingerprint: str = Field(index=True)
    duplicate_guard_key: str = Field(index=True)
    request_checksum: str
    idempotency_key: str = Field(index=True)
    gateway_charge_id: str = Field(index=True)
    gateway_status: str
    failure_reason: str | None = None
    card_brand: str | None = None
    card_last4: str | None = None
    receipt_id: UUID | None = None
    receipt_number: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), index=True)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
