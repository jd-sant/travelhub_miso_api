from datetime import UTC, datetime, timedelta
from decimal import Decimal

from domain.schemas.property_service import PropertyCancellationPolicyResponse
from domain.schemas.reservation import CancellationPolicyType


def _normalize_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(UTC).replace(tzinfo=None)


def calculate_cancellation_refund(
    *,
    total_price: Decimal,
    check_in_date: datetime,
    policy: PropertyCancellationPolicyResponse,
    now: datetime | None = None,
) -> tuple[Decimal, Decimal, bool, datetime, CancellationPolicyType]:
    normalized_check_in = _normalize_datetime(check_in_date)
    normalized_now = _normalize_datetime(now or datetime.now(UTC))
    eligible_until = normalized_check_in - timedelta(hours=policy.minimum_notice_hours)
    within_window = normalized_now <= eligible_until
    refund_type = CancellationPolicyType(policy.policy_type)

    if refund_type == CancellationPolicyType.full_refund:
        refund_amount = total_price if within_window else Decimal("0.00")
        penalty_amount = Decimal("0.00") if within_window else total_price
    elif refund_type == CancellationPolicyType.partial_refund:
        penalty_amount = (
            total_price * (policy.penalty_percentage / Decimal("100"))
        ).quantize(Decimal("0.01"))
        refund_amount = (
            (total_price - penalty_amount).quantize(Decimal("0.01"))
            if within_window
            else Decimal("0.00")
        )
        if not within_window:
            penalty_amount = total_price
    else:
        refund_amount = Decimal("0.00")
        penalty_amount = total_price

    return (
        refund_amount.quantize(Decimal("0.01")),
        penalty_amount.quantize(Decimal("0.01")),
        within_window,
        eligible_until,
        refund_type,
    )
