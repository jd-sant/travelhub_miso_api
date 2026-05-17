from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel


class ReservationInternalNote(SQLModel, table=True):
    __tablename__ = "reservation_internal_note"

    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    reservation_id: UUID = Field(index=True)
    content: str = Field(max_length=1000)
    author_user_id: UUID = Field(index=True)
    author_name: str | None = Field(default=None, max_length=255)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
