from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class PaymentAuditLogRecord(BaseModel):
    traveler_id: UUID | None = None
    payment_id: UUID | None = None
    checkout_session_id: UUID | None = None
    entity_type: str
    entity_id: str
    action: str
    ip_address: str | None = None
    payload: dict
    created_at: datetime
