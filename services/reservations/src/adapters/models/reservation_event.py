from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


class ReservationEvent(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    reservation_id: UUID = Field(index=True)
    event_type: str = Field(index=True, max_length=64)
    actor_user_id: UUID | None = Field(default=None, index=True)
    source_ip: str | None = Field(default=None, max_length=64)
    result: str = Field(default="success", index=True, max_length=32)
    before_payload: dict | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    after_payload: dict | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC), index=True)
