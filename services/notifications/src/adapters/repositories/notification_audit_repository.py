from sqlmodel import Session

from adapters.models.notification_audit_log import NotificationAuditLog
from core.privacy import sanitize_sensitive_data
from domain.ports.notification_audit_repository import NotificationAuditRepository
from domain.schemas.notification import NotificationAuditLogRecord


class SQLModelNotificationAuditRepository(NotificationAuditRepository):
    def __init__(self, session: Session):
        self.session = session

    def add_log(self, log: NotificationAuditLogRecord) -> None:
        model = NotificationAuditLog(
            notification_id=log.notification_id,
            traveler_id=log.traveler_id,
            entity_type=log.entity_type,
            entity_id=log.entity_id,
            action=log.action,
            ip_address=log.ip_address,
            payload=sanitize_sensitive_data(log.payload),
            created_at=log.created_at,
        )
        self.session.add(model)
        self.session.commit()
