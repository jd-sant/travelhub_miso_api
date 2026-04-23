from datetime import datetime, timezone
from uuid import uuid4

from fastapi import Header


def resolve_correlation_id(x_correlation_id: str | None = Header(default=None)) -> str:
    if x_correlation_id and x_correlation_id.strip():
        return x_correlation_id.strip()
    return str(uuid4())


def refund_latency_seconds(*, created_at: datetime, now: datetime | None = None) -> int:
    current = _as_utc(now or datetime.now(timezone.utc))
    created = _as_utc(created_at)
    return max(0, int((current - created).total_seconds()))


def refund_sla_breach_count(*, now: datetime, sla_deadline_at: datetime) -> int:
    return 1 if _as_utc(now) > _as_utc(sla_deadline_at) else 0


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
