from datetime import date, datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class NotificationStatus(str, Enum):
    pending = "pending"
    sent = "sent"
    failed = "failed"


class DeliveryAttemptStatus(str, Enum):
    sent = "sent"
    failed = "failed"


class PaymentConfirmationRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    payment_id: UUID
    source_ip: str | None = Field(default=None, max_length=64)
    payment_confirmed_at: datetime | None = Field(
        default=None,
        description="Instante en el que payments marcó el pago como confirmado; usado para medir latencia SLA de 30s.",
    )


class ReservationUpdateRequest(BaseModel):
    traveler_id: UUID
    reservation_id: UUID
    status: str = Field(min_length=3, max_length=32)
    reason: str = Field(min_length=3, max_length=500)
    source_ip: str | None = Field(default=None, max_length=64)
    refund_requested: bool = False
    refund_amount_in_cents: int | None = None


class NotificationRecord(BaseModel):
    notification_id: UUID
    traveler_id: UUID
    reservation_id: UUID
    payment_id: UUID | None = None
    channel: str
    template_code: str
    status: NotificationStatus
    subject: str
    recipient_email: str
    recipient_name: str
    payload: dict
    created_at: datetime
    updated_at: datetime


class PaymentConfirmationSourceRecord(BaseModel):
    payment_id: UUID
    reservation_id: UUID
    traveler_id: UUID
    status: str
    amount_in_cents: int = Field(gt=0)
    currency: str = Field(min_length=3, max_length=3)
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
    cancellation_policy: str | None = None


class TravelerProfileRecord(BaseModel):
    traveler_id: UUID
    email: str = Field(min_length=5, max_length=255)
    full_name: str = Field(min_length=2, max_length=100)


class NotificationDeliveryAttemptRecord(BaseModel):
    attempt_id: UUID
    notification_id: UUID
    attempt_number: int
    status: DeliveryAttemptStatus
    provider_message_id: str | None = None
    failure_reason: str | None = None
    created_at: datetime


class NotificationAuditLogRecord(BaseModel):
    notification_id: UUID | None = None
    traveler_id: UUID | None = None
    entity_type: str
    entity_id: str
    action: str
    ip_address: str | None = None
    payload: dict
    created_at: datetime


class NotificationResponse(BaseModel):
    notification_id: UUID
    status: NotificationStatus
    recipient_email: str
    subject: str
    payment_id: UUID | None = None
    reservation_id: UUID
    created_at: datetime
    updated_at: datetime
