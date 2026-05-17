from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import Column
from sqlmodel import Field, JSON, SQLModel


class Notification(SQLModel, table=True):
    id: UUID = Field(primary_key=True, index=True)
    traveler_id: UUID = Field(index=True)
    reservation_id: UUID = Field(index=True)
    payment_id: UUID | None = Field(default=None, index=True)
    channel: str = Field(max_length=32, index=True)
    template_code: str = Field(max_length=64, index=True)
    status: str = Field(max_length=32, index=True)
    subject: str = Field(max_length=255)
    recipient_email: str = Field(max_length=255, index=True)
    recipient_name: str = Field(max_length=100)
    payload: dict = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), index=True)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), index=True)
