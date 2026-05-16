import logging
from uuid import UUID

import httpx

from core.config import settings

logger = logging.getLogger(__name__)


def record_sensitive_data_event(
    *,
    action: str,
    resource_type: str,
    pii_fields: list[str],
    source_ip: str,
    actor_user_id: UUID | None = None,
    resource_id: str | None = None,
    country_code: str | None = None,
    metadata: dict | None = None,
) -> None:
    if not settings.privacy_audit_enabled:
        return
    url = f"{settings.security_service_url}/api/v1/internal/privacy/audit"
    payload = {
        "actor_user_id": str(actor_user_id) if actor_user_id else None,
        "action": action,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "pii_fields": pii_fields,
        "source_ip": source_ip,
        "country_code": country_code,
        "metadata": metadata or {},
    }
    try:
        response = httpx.post(
            url,
            json=payload,
            headers={"X-Internal-Api-Key": settings.internal_api_key},
            timeout=settings.service_request_timeout,
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        logger.warning("privacy audit event could not be recorded: %s", exc)
