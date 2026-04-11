from datetime import datetime, timezone
from uuid import UUID

from sqlmodel import Field, SQLModel


class NotificationDeliveryAttempt(SQLModel, table=True):
    id: UUID = Field(primary_key=True, index=True)
    notification_id: UUID = Field(foreign_key="notification.id", index=True)
    attempt_number: int = Field(ge=1)
    status: str = Field(max_length=32, index=True)
    provider_message_id: str | None = Field(default=None, max_length=255)
    failure_reason: str | None = Field(default=None, max_length=255)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), index=True)
