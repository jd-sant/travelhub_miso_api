from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from domain.ports.reservation_command_log_repository import (
    ReservationCommandLogRepository,
)
from domain.ports.reservation_event_repository import ReservationEventRepository
from domain.ports.payment_service_client import PaymentServiceClient
from domain.ports.reservation_repository import ReservationRepository
from domain.schemas.reservation import (
    ReservationCommandType,
    ReservationConfirmResponse,
    ReservationEventCreateRequest,
    ReservationEventResult,
    ReservationEventType,
    ReservationModificationConfirmRequest,
    ReservationModificationPreviewRequest,
)
from domain.use_cases.preview_reservation_modification import (
    PreviewReservationModificationUseCase,
)
from errors import (
    InvalidReservationOperationError,
    PaymentServiceUnavailableError,
    ReservationNotFoundError,
    ReservationOwnershipError,
)


class ConfirmReservationModificationUseCase:
    def __init__(
        self,
        reservation_repository: ReservationRepository,
        event_repository: ReservationEventRepository,
        command_log_repository: ReservationCommandLogRepository,
        payment_service: PaymentServiceClient,
        preview_use_case: PreviewReservationModificationUseCase,
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
        payload: ReservationModificationConfirmRequest,
        *,
        actor_user_id: UUID,
        source_ip: str | None,
        correlation_id: str | None = None,
    ) -> ReservationConfirmResponse:
        cached = self.command_log_repository.get_by_idempotency(
            reservation_id,
            ReservationCommandType.modification_confirm,
            payload.idempotency_key,
        )
        if cached:
            return ReservationConfirmResponse.model_validate(cached)

        reservation_before = self.reservation_repository.get_by_id(reservation_id)
        if not reservation_before:
            raise ReservationNotFoundError("Reservation not found")
        if reservation_before.id_traveler != actor_user_id:
            raise ReservationOwnershipError("Reservation does not belong to traveler")

        preview = self.preview_use_case.execute(
            reservation_id,
            ReservationModificationPreviewRequest(
                check_in_date=payload.check_in_date,
                check_out_date=payload.check_out_date,
                number_of_guests=payload.number_of_guests,
            ),
        )
        if not preview.change_allowed:
            raise InvalidReservationOperationError(
                "; ".join(preview.reasons) or "Modification is not allowed"
            )

        additional_charge_amount = (
            preview.delta_amount if preview.delta_amount > Decimal("0.00") else Decimal("0.00")
        )
        refund_amount = preview.estimated_refund_amount
        payment_dispatch_status = "not_required"

        if additional_charge_amount > Decimal("0.00"):
            try:
                self.payment_service.request_additional_charge(
                    reservation_id=reservation_id,
                    traveler_id=reservation_before.id_traveler,
                    amount_in_cents=self._to_cents(additional_charge_amount),
                    currency=reservation_before.currency,
                    idempotency_key=f"{payload.idempotency_key}:additional-charge",
                    source_ip=source_ip,
                )
                payment_dispatch_status = "additional_charge_requested"
            except PaymentServiceUnavailableError:
                payment_dispatch_status = "additional_charge_pending_retry"
        elif refund_amount > Decimal("0.00"):
            try:
                self.payment_service.request_refund(
                    reservation_id=reservation_id,
                    amount_in_cents=self._to_cents(refund_amount),
                    reason="reservation_modification_refund",
                    idempotency_key=f"{payload.idempotency_key}:refund",
                    source_ip=source_ip,
                )
                payment_dispatch_status = "refund_requested"
            except PaymentServiceUnavailableError:
                payment_dispatch_status = "refund_pending_retry"

        if additional_charge_amount > Decimal("0.00"):
            status_after = "modification_pending_payment"
        elif refund_amount > Decimal("0.00"):
            status_after = "refund_pending"
        else:
            status_after = "modification_confirmed"

        updated = self.reservation_repository.apply_updates(
            reservation_id,
            status=status_after,
            expected_version=reservation_before.version,
            check_in_date=preview.reservation_after_preview.check_in_date,
            check_out_date=preview.reservation_after_preview.check_out_date,
            number_of_guests=preview.reservation_after_preview.number_of_guests,
            total_price=preview.reservation_after_preview.total_price,
            last_policy_snapshot=preview.policy_applied.model_dump_json(),
        )
        if not updated:
            raise ReservationNotFoundError("Reservation not found")

        self.event_repository.add(
            ReservationEventCreateRequest(
                reservation_id=reservation_id,
                event_type=ReservationEventType.modification_confirmed,
                actor_user_id=actor_user_id,
                source_ip=source_ip,
                result=ReservationEventResult.success,
                before_payload=reservation_before.model_dump(mode="json"),
                after_payload={
                    **updated.model_dump(mode="json"),
                    "correlation_id": correlation_id,
                    "payment_dispatch_status": payment_dispatch_status,
                },
            )
        )

        response = ReservationConfirmResponse(
            reservation=updated,
            status_before=reservation_before.status,
            status_after=updated.status,
            action_applied="modification_confirmed",
            idempotency_key=payload.idempotency_key,
            additional_charge_amount=additional_charge_amount,
            refund_amount=refund_amount,
        )
        self.command_log_repository.add(
            reservation_id,
            ReservationCommandType.modification_confirm,
            payload.idempotency_key,
            response.model_dump(mode="json"),
        )
        return response
