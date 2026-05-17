from typing import Optional
from uuid import UUID

from sqlmodel import Session

from adapters.models.audit_log import AuditLog
from domain.ports.audit_repository import AuditRepository as AuditRepositoryPort


class SQLModelAuditRepository(AuditRepositoryPort):
    def __init__(self, session: Session):
        self.session = session

    def record(
        self,
        entity_type: str,
        action: str,
        ip_address: str,
        user_id: Optional[UUID] = None,
        entity_id: Optional[UUID] = None,
    ) -> None:
        entry = AuditLog(
            user_id=user_id,
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            ip_address=ip_address,
        )
        self.session.add(entry)
        self.session.commit()
