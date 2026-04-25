from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PaymentStatus(str, Enum):
    pending = "pending"
    confirmed = "confirmed"
    failed = "failed"


class PaymentByReservation(BaseModel):
    reservation_id: UUID
    amount_in_cents: int
    currency: str


class PaymentsByReservationsRequest(BaseModel):
    reservation_ids: list[UUID] = Field(default_factory=list)
    status: PaymentStatus = PaymentStatus.confirmed


class PaymentsByReservationsResponse(BaseModel):
    items: list[PaymentByReservation] = Field(default_factory=list)
    available_currencies: list[str] = Field(default_factory=list)


class RefundStatus(str, Enum):
    pending = "pending"
    succeeded = "succeeded"
    failed = "failed"


class ReservationConfirmationOutboxStatus(str, Enum):
    pending = "pending"
    succeeded = "succeeded"
    failed = "failed"


class PaymentProcessingOutboxStatus(str, Enum):
    pending = "pending"
    processing = "processing"
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


class ReservationRefundRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reservation_id: UUID
    amount_in_cents: int = Field(gt=0)
    reason: str = Field(min_length=4, max_length=255)
    idempotency_key: str = Field(min_length=8, max_length=255)


class AdditionalChargeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reservation_id: UUID
    traveler_id: UUID
    amount_in_cents: int = Field(gt=0)
    currency: str = Field(min_length=3, max_length=3)
    idempotency_key: str = Field(min_length=8, max_length=255)
    payment_method_token: str = Field(default="pm_tok_visa_ok", min_length=4, max_length=255)

    @field_validator("currency")
    @classmethod
    def uppercase_internal_currency(cls, value: str) -> str:
        return value.upper()


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
    gateway_charge_id: str | None = None
    gateway_status: str | None = None
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
    gateway_charge_id: str | None = None
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


class PaymentProcessingOutboxRecord(BaseModel):
    outbox_id: UUID
    payment_id: UUID
    checkout_session_id: UUID
    status: PaymentProcessingOutboxStatus
    attempt_count: int
    max_attempts: int
    next_retry_at: datetime
    source_ip: str | None = None
    last_error: str | None = None
    last_attempt_at: datetime | None = None
    processed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class PaymentProcessingRetryResponse(BaseModel):
    processed_count: int
    succeeded_count: int
    failed_count: int
    pending_count: int


class ReservationConfirmationRetryResponse(BaseModel):
    processed_count: int
    succeeded_count: int
    failed_count: int
    pending_count: int


class ReservationRefundRequest(BaseModel):
    reservation_id: UUID
    reason: str = Field(min_length=3, max_length=255)
    source_ip: str | None = Field(default=None, max_length=64)


class ReservationRefundResponse(BaseModel):
    refund_id: UUID
    payment_id: UUID
    reservation_id: UUID
    amount_in_cents: int
    currency: str
    status: RefundStatus
    gateway_refund_id: str | None = None
    reason: str = Field(min_length=3, max_length=255)
    created_at: datetime
    updated_at: datetime


class PaymentRefundRetryResponse(BaseModel):
    processed_count: int
    succeeded_count: int
    failed_count: int
    pending_count: int
