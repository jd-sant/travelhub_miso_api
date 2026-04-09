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
    model_config = ConfigDict(extra="forbid")

    reservation_id: UUID
    traveler_id: UUID
    payment_id: UUID
    recipient_email: str = Field(min_length=5, max_length=255)
    recipient_name: str = Field(min_length=2, max_length=100)
    property_name: str | None = Field(default=None, min_length=2, max_length=255)
    check_in_date: date | None = None
    check_out_date: date | None = None
    amount_in_cents: int = Field(gt=0)
    currency: str = Field(min_length=3, max_length=3)
    receipt_id: UUID | None = None
    receipt_number: str | None = None
    source_ip: str | None = Field(default=None, max_length=64)


class NotificationRecord(BaseModel):
    notification_id: UUID
    traveler_id: UUID
    reservation_id: UUID
    payment_id: UUID
    channel: str
    template_code: str
    status: NotificationStatus
    subject: str
    recipient_email: str
    recipient_name: str
    payload: dict
    created_at: datetime
    updated_at: datetime


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
    payment_id: UUID
    reservation_id: UUID
    created_at: datetime
    updated_at: datetime
