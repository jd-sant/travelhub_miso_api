from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel


class DeviceToken(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    user_id: UUID = Field(index=True)
    token: str = Field(max_length=512, unique=True, index=True)
    platform: str = Field(max_length=16, index=True)
    app_version: str | None = Field(default=None, max_length=32)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), index=True
    )
    last_seen_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), index=True
    )
    revoked_at: datetime | None = Field(default=None, index=True)
