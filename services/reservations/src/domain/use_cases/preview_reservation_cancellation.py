from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from domain.schemas.reservation import (
    CancellationPolicyType,
    ReservationCancellationPreviewResponse,
    ReservationEventResult,
    ReservationEventType,
)
from domain.services.cancellation_policy_refund import calculate_cancellation_refund
from domain.use_cases.reservation_preview_base import ReservationPreviewBaseUseCase


class PreviewReservationCancellationUseCase(ReservationPreviewBaseUseCase):
    def execute(self, reservation_id: UUID) -> ReservationCancellationPreviewResponse:
        reservation = self._get_reservation(reservation_id)
        policy = self._get_policy(reservation.id_property)
        policy_snapshot = self._build_policy_snapshot(policy)

        reasons: list[str] = []
        if reservation.status != "confirmed":
            reasons.append("Reservation must be confirmed")

        normalized_reservation_check_in = self._normalize_datetime(reservation.check_in_date)
        eligible_until = normalized_reservation_check_in - timedelta(
            hours=policy.minimum_notice_hours
        )
        if datetime.now(UTC).replace(tzinfo=None) > eligible_until:
            reasons.append("Cancellation window has expired")

        change_allowed = not reasons
        refund_amount, penalty_amount, _, _, refund_type = calculate_cancellation_refund(
            total_price=reservation.total_price,
            check_in_date=reservation.check_in_date,
            policy=policy,
        )
        if not change_allowed:
            if refund_type == CancellationPolicyType.full_refund:
                penalty_amount = reservation.total_price
            refund_amount = Decimal("0.00")

        after_payload = {
            "reservation_id": str(reservation.id),
            "policy_type": refund_type.value,
            "refund_amount": str(refund_amount),
            "penalty_amount": str(penalty_amount),
            "eligible_until": eligible_until.isoformat(),
            "change_allowed": change_allowed,
            "reasons": reasons,
        }

        self._record_event(
            reservation_id=reservation.id,
            event_type=ReservationEventType.cancellation_previewed,
            result=ReservationEventResult.success if change_allowed else ReservationEventResult.rejected,
            before_payload=reservation.model_dump(mode="json"),
            after_payload=after_payload,
        )

        return ReservationCancellationPreviewResponse(
            reservation_id=reservation.id,
            policy_applied=policy_snapshot,
            refund_amount=refund_amount.quantize(Decimal("0.01")),
            penalty_amount=penalty_amount.quantize(Decimal("0.01")),
            refund_type=refund_type,
            eligible_until=eligible_until,
            change_allowed=change_allowed,
            reasons=reasons,
        )
