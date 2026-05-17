from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel


class AuditLog(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    user_id: Optional[UUID] = Field(default=None)
    entity_type: str
    entity_id: Optional[UUID] = Field(default=None)
    action: str
    ip_address: str
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
