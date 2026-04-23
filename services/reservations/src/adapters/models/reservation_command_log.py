from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import JSON, Column, UniqueConstraint
from sqlmodel import Field, SQLModel


class ReservationCommandLog(SQLModel, table=True):
    __tablename__ = "reservation_command_logs"
    __table_args__ = (
        UniqueConstraint(
            "reservation_id",
            "command_type",
            "idempotency_key",
            name="uq_reservation_command_idempotency",
        ),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    reservation_id: UUID = Field(index=True)
    command_type: str = Field(max_length=64, index=True)
    idempotency_key: str = Field(max_length=128, index=True)
    response_payload: dict = Field(sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC), index=True)
