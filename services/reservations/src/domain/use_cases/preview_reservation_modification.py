from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from domain.schemas.reservation import (
    ReservationEventResult,
    ReservationEventType,
    ReservationModificationPreviewRequest,
    ReservationModificationPreviewResponse,
)
from domain.use_cases.reservation_preview_base import ReservationPreviewBaseUseCase


class PreviewReservationModificationUseCase(ReservationPreviewBaseUseCase):
    def execute(
        self,
        reservation_id: UUID,
        payload: ReservationModificationPreviewRequest,
    ) -> ReservationModificationPreviewResponse:
        reservation = self._get_reservation(reservation_id)
        property_details = self._get_property(reservation.id_property)
        policy = self._get_policy(reservation.id_property)

        normalized_check_in = self._normalize_datetime(payload.check_in_date)
        normalized_check_out = self._normalize_datetime(payload.check_out_date)

        reasons: list[str] = []
        if reservation.status != "confirmed":
            reasons.append("Reservation must be confirmed")
        if normalized_check_in >= normalized_check_out:
            reasons.append("Check-out date must be after check-in date")
        if payload.number_of_guests > property_details.max_guests:
            reasons.append(
                f"Requested guests exceed property capacity of {property_details.max_guests}"
            )

        eligible_until = reservation.check_in_date - timedelta(
            hours=policy.minimum_notice_hours
        )
        if datetime.now(UTC).replace(tzinfo=None) > eligible_until:
            reasons.append("Modification window has expired")

        is_available = self.reservation_repository.check_room_availability(
            reservation.id_room,
            normalized_check_in,
            normalized_check_out,
            exclude_reservation_id=reservation.id,
        )
        if not is_available:
            reasons.append("Room is not available for the selected dates")

        price_before = self._build_price_breakdown(reservation.total_price, reservation.currency)
        price_after_total = self._calculate_price_with_taxes(
            reservation.currency,
            normalized_check_in,
            normalized_check_out,
        )
        price_after = self._build_price_breakdown(price_after_total, reservation.currency)
        delta_amount = (price_after_total - reservation.total_price).quantize(
            Decimal("0.01")
        )
        requires_additional_charge = delta_amount > 0
        estimated_refund_amount = (
            (-delta_amount).quantize(Decimal("0.01")) if delta_amount < 0 else Decimal("0.00")
        )
        change_allowed = not reasons

        reservation_after_preview = reservation.model_copy(
            update={
                "check_in_date": normalized_check_in,
                "check_out_date": normalized_check_out,
                "number_of_guests": payload.number_of_guests,
                "total_price": price_after_total,
            }
        )

        after_payload = reservation_after_preview.model_dump(mode="json")
        after_payload.update(
            {
                "delta_amount": str(delta_amount),
                "requires_additional_charge": requires_additional_charge,
                "estimated_refund_amount": str(estimated_refund_amount),
                "change_allowed": change_allowed,
                "reasons": reasons,
            }
        )

        self._record_event(
            reservation_id=reservation.id,
            event_type=ReservationEventType.modification_previewed,
            result=ReservationEventResult.success if change_allowed else ReservationEventResult.rejected,
            before_payload=reservation.model_dump(mode="json"),
            after_payload=after_payload,
        )

        return ReservationModificationPreviewResponse(
            reservation_id=reservation.id,
            reservation_before=reservation,
            reservation_after_preview=reservation_after_preview,
            price_before=price_before,
            price_after=price_after,
            delta_amount=delta_amount,
            requires_additional_charge=requires_additional_charge,
            estimated_refund_amount=estimated_refund_amount,
            policy_applied=self._build_policy_snapshot(policy),
            change_allowed=change_allowed,
            reasons=reasons,
        )
