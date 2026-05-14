from datetime import datetime, timezone
from uuid import UUID

from sqlmodel import Field, SQLModel


class NotificationPreference(SQLModel, table=True):
    user_id: UUID = Field(primary_key=True, index=True)
    status_changes_enabled: bool = Field(default=True)
    arrival_reminders_enabled: bool = Field(default=True)
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), index=True
    )
