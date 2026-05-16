from sqlmodel import Session, desc, select

from adapters.models.sensitive_data_audit_log import SensitiveDataAuditLog
from core.config import settings
from core.privacy import build_entry_hash, resolve_data_region
from domain.ports.privacy_audit_repository import PrivacyAuditRepository
from domain.schemas.privacy import SensitiveDataAuditRequest, SensitiveDataAuditResponse


class SQLModelPrivacyAuditRepository(PrivacyAuditRepository):
    def __init__(self, session: Session):
        self.session = session

    def record(self, payload: SensitiveDataAuditRequest) -> SensitiveDataAuditResponse:
        latest = self.session.exec(
            select(SensitiveDataAuditLog).order_by(
                desc(SensitiveDataAuditLog.created_at),
                desc(SensitiveDataAuditLog.id),
            )
        ).first()
        data_region = resolve_data_region(
            payload.country_code,
            policies=settings.data_residency_policies,
            default_region=settings.default_data_region,
        )
        entry = SensitiveDataAuditLog(
            actor_user_id=payload.actor_user_id,
            action=payload.action,
            resource_type=payload.resource_type,
            resource_id=payload.resource_id,
            pii_fields=sorted(
                {field.strip().lower() for field in payload.pii_fields if field.strip()}
            ),
            source_ip=payload.source_ip,
            country_code=payload.country_code.upper() if payload.country_code else None,
            data_region=data_region,
            event_metadata=payload.metadata,
            previous_hash=latest.entry_hash if latest else None,
            entry_hash="",
        )
        entry.entry_hash = build_entry_hash(
            previous_hash=entry.previous_hash,
            actor_user_id=str(entry.actor_user_id) if entry.actor_user_id else None,
            action=entry.action,
            resource_type=entry.resource_type,
            resource_id=entry.resource_id,
            pii_fields=entry.pii_fields,
            source_ip=entry.source_ip,
            country_code=entry.country_code,
            data_region=entry.data_region,
            metadata=entry.event_metadata,
            created_at_iso=entry.created_at.isoformat(),
        )
        self.session.add(entry)
        self.session.commit()
        self.session.refresh(entry)
        return SensitiveDataAuditResponse(
            id=entry.id,
            actor_user_id=entry.actor_user_id,
            action=entry.action,
            resource_type=entry.resource_type,
            resource_id=entry.resource_id,
            pii_fields=entry.pii_fields,
            source_ip=entry.source_ip,
            country_code=entry.country_code,
            data_region=entry.data_region,
            previous_hash=entry.previous_hash,
            entry_hash=entry.entry_hash,
            created_at=entry.created_at,
        )
