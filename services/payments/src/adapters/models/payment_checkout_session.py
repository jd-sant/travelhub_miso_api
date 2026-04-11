from datetime import date, datetime, timezone
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel


class PaymentCheckoutSession(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    reservation_id: UUID = Field(index=True)
    traveler_id: UUID = Field(index=True)
    provider_code: str = Field(index=True, max_length=64)
    amount_in_cents: int
    currency: str = Field(max_length=3)
    property_name: str | None = None
    check_in_date: date | None = None
    check_out_date: date | None = None
    idempotency_key: str = Field(index=True, unique=True)
    confirmation_token_id: str | None = Field(default=None, index=True)
    stripe_payment_intent_id: str | None = Field(default=None, index=True)
    status: str = Field(index=True)
    payment_id: UUID | None = Field(default=None, foreign_key="payment.id", index=True)
    client_secret: str | None = None
    last_error_message: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), index=True)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
