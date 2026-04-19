from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from domain.schemas.reservation import (
    CancellationPolicyType,
    ReservationCancellationPreviewResponse,
    ReservationEventResult,
    ReservationEventType,
)
from domain.use_cases.reservation_preview_base import ReservationPreviewBaseUseCase


class PreviewReservationCancellationUseCase(ReservationPreviewBaseUseCase):
    def execute(self, reservation_id: UUID) -> ReservationCancellationPreviewResponse:
        reservation = self._get_reservation(reservation_id)
        policy = self._get_policy(reservation.id_property)
        policy_snapshot = self._build_policy_snapshot(policy)

        reasons: list[str] = []
        if reservation.status != "confirmed":
            reasons.append("Reservation must be confirmed")

        eligible_until = reservation.check_in_date - timedelta(
            hours=policy.minimum_notice_hours
        )
        if datetime.now(UTC).replace(tzinfo=None) > eligible_until:
            reasons.append("Cancellation window has expired")

        change_allowed = not reasons
        refund_type = CancellationPolicyType(policy.policy_type)

        if refund_type == CancellationPolicyType.full_refund:
            refund_amount = reservation.total_price if change_allowed else Decimal("0.00")
            penalty_amount = Decimal("0.00") if change_allowed else reservation.total_price
        elif refund_type == CancellationPolicyType.partial_refund:
            penalty_amount = (
                reservation.total_price * (policy.penalty_percentage / Decimal("100"))
            ).quantize(Decimal("0.01"))
            refund_amount = (
                (reservation.total_price - penalty_amount).quantize(Decimal("0.01"))
                if change_allowed
                else Decimal("0.00")
            )
            if not change_allowed:
                penalty_amount = reservation.total_price
        else:
            refund_amount = Decimal("0.00")
            penalty_amount = reservation.total_price

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
