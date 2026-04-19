from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PaymentStatus(str, Enum):
    confirmed = "confirmed"
    failed = "failed"


class ReservationConfirmationOutboxStatus(str, Enum):
    pending = "pending"
    succeeded = "succeeded"
    failed = "failed"


class PaymentRefundStatus(str, Enum):
    pending = "pending"
    succeeded = "succeeded"
    failed = "failed"


class PaymentChargeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reservation_id: UUID
    traveler_id: UUID
    payment_method_token: str = Field(min_length=4, max_length=255)
    amount_in_cents: int = Field(gt=0)
    currency: str = Field(min_length=3, max_length=3)
    idempotency_key: str = Field(min_length=8, max_length=255)
    request_checksum: str | None = Field(default=None, min_length=32, max_length=128)

    @field_validator("currency")
    @classmethod
    def uppercase_currency(cls, value: str) -> str:
        return value.upper()


class PaymentRefundCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    payment_id: UUID
    amount_in_cents: int = Field(gt=0)
    reason: str = Field(min_length=4, max_length=255)
    idempotency_key: str = Field(min_length=8, max_length=255)


class GatewayChargeResult(BaseModel):
    status: PaymentStatus
    gateway_charge_id: str
    gateway_status: str
    failure_reason: str | None = None
    card_brand: str | None = None
    card_last4: str | None = None


class PaymentChargeResponse(BaseModel):
    payment_id: UUID
    reservation_id: UUID
    traveler_id: UUID
    provider_code: str
    status: PaymentStatus
    amount_in_cents: int
    currency: str
    gateway_charge_id: str
    gateway_status: str
    idempotency_key: str
    request_fingerprint: str
    duplicate_guard_key: str
    request_checksum: str
    payment_method_token_hash: str
    receipt_id: UUID | None = None
    receipt_number: str | None = None
    failure_reason: str | None = None
    card_brand: str | None = None
    card_last4: str | None = None
    created_at: datetime
    updated_at: datetime


class PaymentEventResponse(BaseModel):
    event_id: UUID
    payment_id: UUID
    event_type: str
    payload: dict
    created_at: datetime


class PaymentPublicResponse(BaseModel):
    payment_id: UUID
    reservation_id: UUID
    provider_code: str
    status: PaymentStatus
    amount_in_cents: int
    currency: str
    gateway_charge_id: str
    receipt_id: UUID | None = None
    receipt_number: str | None = None
    failure_reason: str | None = None


class PaymentRefundResponse(BaseModel):
    refund_id: UUID
    payment_id: UUID
    reservation_id: UUID
    traveler_id: UUID
    amount_in_cents: int
    currency: str
    reason: str
    idempotency_key: str
    status: PaymentRefundStatus
    retry_count: int
    max_attempts: int
    sla_deadline_at: datetime
    next_retry_at: datetime
    last_error: str | None = None
    processed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class PaymentRefundPublicResponse(BaseModel):
    refund_id: UUID
    payment_id: UUID
    reservation_id: UUID
    traveler_id: UUID
    amount_in_cents: int
    currency: str
    reason: str
    status: PaymentRefundStatus
    retry_count: int
    max_attempts: int
    sla_deadline_at: datetime
    next_retry_at: datetime
    last_error: str | None = None
    processed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class ReservationConfirmationOutboxRecord(BaseModel):
    outbox_id: UUID
    payment_id: UUID
    reservation_id: UUID
    status: ReservationConfirmationOutboxStatus
    attempt_count: int
    max_attempts: int
    next_retry_at: datetime
    last_error: str | None = None
    last_attempt_at: datetime | None = None
    processed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class ReservationConfirmationRetryResponse(BaseModel):
    processed_count: int
    succeeded_count: int
    failed_count: int
    pending_count: int


class PaymentRefundRetryResponse(BaseModel):
    processed_count: int
    succeeded_count: int
    failed_count: int
    pending_count: int
