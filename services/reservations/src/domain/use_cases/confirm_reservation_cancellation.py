from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from domain.ports.reservation_command_log_repository import (
    ReservationCommandLogRepository,
)
from domain.ports.reservation_event_repository import ReservationEventRepository
from domain.ports.payment_service_client import PaymentServiceClient
from domain.ports.reservation_repository import ReservationRepository
from domain.schemas.reservation import (
    ReservationCancellationConfirmRequest,
    ReservationCommandType,
    ReservationConfirmResponse,
    ReservationEventCreateRequest,
    ReservationEventResult,
    ReservationEventType,
)
from domain.use_cases.preview_reservation_cancellation import (
    PreviewReservationCancellationUseCase,
)
from errors import (
    InvalidReservationOperationError,
    PaymentServiceUnavailableError,
    ReservationNotFoundError,
    ReservationOwnershipError,
)


class ConfirmReservationCancellationUseCase:
    def __init__(
        self,
        reservation_repository: ReservationRepository,
        event_repository: ReservationEventRepository,
        command_log_repository: ReservationCommandLogRepository,
        payment_service: PaymentServiceClient,
        preview_use_case: PreviewReservationCancellationUseCase,
    ):
        self.reservation_repository = reservation_repository
        self.event_repository = event_repository
        self.command_log_repository = command_log_repository
        self.payment_service = payment_service
        self.preview_use_case = preview_use_case

    @staticmethod
    def _to_cents(amount: Decimal) -> int:
        return int((amount * Decimal("100")).quantize(Decimal("1"), rounding=ROUND_HALF_UP))

    def execute(
        self,
        reservation_id: UUID,
        payload: ReservationCancellationConfirmRequest,
        *,
        actor_user_id: UUID,
        source_ip: str | None,
        correlation_id: str | None = None,
    ) -> ReservationConfirmResponse:
        cached = self.command_log_repository.get_by_idempotency(
            reservation_id,
            ReservationCommandType.cancellation_confirm,
            payload.idempotency_key,
        )
        if cached:
            return ReservationConfirmResponse.model_validate(cached)

        reservation_before = self.reservation_repository.get_by_id(reservation_id)
        if not reservation_before:
            raise ReservationNotFoundError("Reservation not found")
        if reservation_before.id_traveler != actor_user_id:
            raise ReservationOwnershipError("Reservation does not belong to traveler")

        preview = self.preview_use_case.execute(reservation_id)
        if not preview.change_allowed:
            raise InvalidReservationOperationError(
                "; ".join(preview.reasons) or "Cancellation is not allowed"
            )

        refund_amount = preview.refund_amount
        refund_dispatch_status = "not_required"

        if refund_amount > Decimal("0.00"):
            try:
                self.payment_service.request_refund(
                    reservation_id=reservation_id,
                    amount_in_cents=self._to_cents(refund_amount),
                    reason=payload.reason or "reservation_cancellation_refund",
                    idempotency_key=f"{payload.idempotency_key}:refund",
                    source_ip=source_ip,
                )
                refund_dispatch_status = "requested"
            except PaymentServiceUnavailableError:
                # Keep reservation in cancel_requested for retry/callback orchestration.
                refund_dispatch_status = "pending_retry"

        status_after = "cancel_requested" if refund_amount > Decimal("0.00") else "cancelled"
        cancelled_at = datetime.now(UTC).replace(tzinfo=None)

        updated = self.reservation_repository.apply_updates(
            reservation_id,
            status=status_after,
            expected_version=reservation_before.version,
            last_policy_snapshot=preview.policy_applied.model_dump_json(),
            cancelled_at=cancelled_at if status_after == "cancelled" else None,
            cancellation_reason=payload.reason,
        )
        if not updated:
            raise ReservationNotFoundError("Reservation not found")

        after_payload = updated.model_dump(mode="json")
        after_payload["refund_amount"] = str(refund_amount)
        after_payload["correlation_id"] = correlation_id
        after_payload["refund_dispatch_status"] = refund_dispatch_status

        self.event_repository.add(
            ReservationEventCreateRequest(
                reservation_id=reservation_id,
                event_type=ReservationEventType.cancellation_confirmed,
                actor_user_id=actor_user_id,
                source_ip=source_ip,
                result=ReservationEventResult.success,
                before_payload=reservation_before.model_dump(mode="json"),
                after_payload=after_payload,
            )
        )

        response = ReservationConfirmResponse(
            reservation=updated,
            status_before=reservation_before.status,
            status_after=updated.status,
            action_applied="cancellation_confirmed",
            idempotency_key=payload.idempotency_key,
            additional_charge_amount=Decimal("0.00"),
            refund_amount=refund_amount,
        )
        self.command_log_repository.add(
            reservation_id,
            ReservationCommandType.cancellation_confirm,
            payload.idempotency_key,
            response.model_dump(mode="json"),
        )
        return response
