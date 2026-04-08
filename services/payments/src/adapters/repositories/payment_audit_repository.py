from sqlmodel import Session

from adapters.models.payment_audit_log import PaymentAuditLog
from domain.ports.payment_audit_repository import PaymentAuditRepository
from domain.schemas.audit import PaymentAuditLogRecord


class SQLModelPaymentAuditRepository(PaymentAuditRepository):
    def __init__(self, session: Session):
        self.session = session

    def add_log(self, log: PaymentAuditLogRecord) -> None:
        model = PaymentAuditLog(
            traveler_id=log.traveler_id,
            payment_id=log.payment_id,
            checkout_session_id=log.checkout_session_id,
            entity_type=log.entity_type,
            entity_id=log.entity_id,
            action=log.action,
            ip_address=log.ip_address,
            payload=log.payload,
            created_at=log.created_at,
        )
        self.session.add(model)
        self.session.commit()
