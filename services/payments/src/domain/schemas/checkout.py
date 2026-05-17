from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PaymentCheckoutSessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reservation_id: UUID
    traveler_id: UUID
    amount_in_cents: int = Field(gt=0)
    currency: str = Field(min_length=3, max_length=3)
    property_name: str | None = Field(default=None, min_length=2, max_length=255)
    check_in_date: date | None = None
    check_out_date: date | None = None

    @field_validator("currency")
    @classmethod
    def uppercase_currency(cls, value: str) -> str:
        return value.upper()


class PaymentCheckoutSessionResponse(BaseModel):
    payment_transaction_id: UUID
    provider_code: str
    amount_in_cents: int
    currency: str
    publishable_key: str
    stripe_enabled: bool


class PaymentCheckoutSessionRecord(BaseModel):
    payment_transaction_id: UUID
    reservation_id: UUID
    traveler_id: UUID
    provider_code: str
    amount_in_cents: int
    currency: str
    property_name: str | None = None
    check_in_date: date | None = None
    check_out_date: date | None = None
    idempotency_key: str
    confirmation_token_id: str | None = None
    payment_intent_id: str | None = None
    status: str
    payment_id: UUID | None = None
    client_secret: str | None = None
    error: str | None = None
    created_at: datetime
    updated_at: datetime


class PaymentFinalizeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    payment_transaction_id: UUID
    confirmation_token_id: str = Field(min_length=1, max_length=255)


class PaymentFinalizeResponse(BaseModel):
    status: str
    payment_id: UUID | None = None
    payment_intent_id: str | None = None
    client_secret: str | None = None
    error: str | None = None


class PaymentCheckoutStatusResponse(BaseModel):
    payment_transaction_id: UUID
    status: str
    payment_id: UUID | None = None
    payment_intent_id: str | None = None
    error: str | None = None
    updated_at: datetime


class PaymentsConfigResponse(BaseModel):
    provider: str
    stripe_enabled: bool
    publishable_key: str


class PaymentConfirmationSummaryResponse(BaseModel):
    payment_id: UUID
    reservation_id: UUID
    traveler_id: UUID
    status: str
    amount_in_cents: int
    currency: str
    receipt_id: UUID | None = None
    receipt_number: str | None = None
    property_name: str | None = None
    property_address: str | None = None
    check_in_date: date | None = None
    check_out_date: date | None = None
    guests_count: int | None = None
    nights: int | None = None
    nightly_rate_in_cents: int | None = None
    taxes_in_cents: int | None = None
    total_in_cents: int | None = None
    accommodation_in_cents: int | None = None
    cleaning_fee_in_cents: int | None = None
    service_fee_in_cents: int | None = None
    cancellation_policy: str | None = None
