from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import Column
from sqlmodel import Field, JSON, SQLModel


class PaymentEvent(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    payment_id: UUID = Field(foreign_key="payment.id", index=True)
    event_type: str = Field(index=True)
    payload: dict = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), index=True)
