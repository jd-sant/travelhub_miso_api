from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import Column
from sqlmodel import Field, JSON, SQLModel


class PaymentAuditLog(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    traveler_id: UUID | None = Field(default=None, index=True)
    payment_id: UUID | None = Field(default=None, foreign_key="payment.id", index=True)
    checkout_session_id: UUID | None = Field(
        default=None,
        foreign_key="paymentcheckoutsession.id",
        index=True,
    )
    entity_type: str = Field(index=True, max_length=64)
    entity_id: str = Field(index=True, max_length=64)
    action: str = Field(index=True, max_length=128)
    ip_address: str | None = Field(default=None, max_length=64)
    payload: dict = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), index=True)
