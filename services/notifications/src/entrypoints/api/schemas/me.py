from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class DeviceRegistrationRequest(BaseModel):
    token: str = Field(min_length=10, max_length=512)
    platform: str = Field(pattern="^(android|ios)$")
    app_version: str | None = Field(default=None, max_length=32)


class NotificationPreferenceResponse(BaseModel):
    status_changes_enabled: bool
    arrival_reminders_enabled: bool


class NotificationPreferenceUpdateRequest(BaseModel):
    status_changes_enabled: bool | None = None
    arrival_reminders_enabled: bool | None = None


class NotificationListItem(BaseModel):
    id: UUID
    notification_id: UUID | None
    title: str
    body: str
    entity_type: str
    entity_id: str
    delivery_status: str
    created_at: datetime
    is_read: bool


class NotificationListResponse(BaseModel):
    items: list[NotificationListItem]
    next_cursor: str | None = None
