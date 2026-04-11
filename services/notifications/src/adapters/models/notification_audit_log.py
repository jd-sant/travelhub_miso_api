from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import Column
from sqlmodel import Field, JSON, SQLModel


class NotificationAuditLog(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    notification_id: UUID | None = Field(default=None, foreign_key="notification.id", index=True)
    traveler_id: UUID | None = Field(default=None, index=True)
    entity_type: str = Field(max_length=64, index=True)
    entity_id: str = Field(max_length=64, index=True)
    action: str = Field(max_length=128, index=True)
    ip_address: str | None = Field(default=None, max_length=64)
    payload: dict = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), index=True)
