from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Column, JSON
from sqlmodel import Field, SQLModel


class SensitiveDataAuditLog(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    actor_user_id: UUID | None = Field(default=None, index=True)
    action: str = Field(max_length=80, index=True)
    resource_type: str = Field(max_length=80, index=True)
    resource_id: str | None = Field(default=None, max_length=120, index=True)
    pii_fields: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    source_ip: str = Field(max_length=120)
    country_code: str | None = Field(default=None, max_length=2, index=True)
    data_region: str = Field(max_length=80, index=True)
    event_metadata: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    previous_hash: str | None = Field(default=None, max_length=64)
    entry_hash: str = Field(max_length=64, unique=True, index=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
