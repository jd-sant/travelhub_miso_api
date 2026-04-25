from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel


class ReservationChange(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    reservation_id: UUID = Field(index=True)
    action: str = Field(max_length=64, index=True)
    previous_status: str = Field(max_length=64, index=True)
    new_status: str = Field(max_length=64, index=True)
    reason: str = Field(max_length=500)
    actor_user_id: UUID | None = Field(default=None, index=True)
    source_ip: str | None = Field(default=None, max_length=64)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC), index=True)
