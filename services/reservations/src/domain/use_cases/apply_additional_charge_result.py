from datetime import datetime
from decimal import Decimal, InvalidOperation
from uuid import UUID

from domain.ports.reservation_event_repository import ReservationEventRepository
from domain.ports.reservation_repository import ReservationRepository
from domain.schemas.reservation import (
    ReservationAdditionalChargeResultRequest,
    ReservationCheckStatusResponse,
    ReservationEventCreateRequest,
    ReservationEventResult,
    ReservationEventType,
)
from errors import (
    InvalidReservationStatusError,
    ReservationNotFoundError,
)


class ApplyAdditionalChargeResultUseCase:
    def __init__(
        self,
        reservation_repository: ReservationRepository,
        event_repository: ReservationEventRepository,
    ):
        self.reservation_repository = reservation_repository
        self.event_repository = event_repository

    @staticmethod
    def _resolve_status_transition(callback_status: str) -> tuple[str, str]:
        if callback_status == "succeeded":
            return "modification_confirmed", "additional_charge_completed"
        return "additional_charge_failed", "additional_charge_failed"

    @staticmethod
    def _to_naive_datetime(value: object) -> datetime:
        if isinstance(value, datetime):
            return value.replace(tzinfo=None) if value.tzinfo is not None else value
        if isinstance(value, str):
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed.replace(tzinfo=None) if parsed.tzinfo is not None else parsed
        raise ValueError("Invalid datetime value")

    def _find_pending_modification_payload(self, reservation_id: UUID) -> dict | None:
        events = self.event_repository.list_by_reservation(reservation_id)
        for event in reversed(events):
            if event.event_type != ReservationEventType.modification_confirmed:
                continue
            payload = event.after_payload or {}
            dispatch_status = payload.get("payment_dispatch_status")
            if dispatch_status not in (
                "additional_charge_requested",
                "additional_charge_pending_retry",
            ):
                continue
            proposal = payload.get("pending_modification")
            if isinstance(proposal, dict):
                return proposal
        return None

    def execute(
        self,
        reservation_id: UUID,
        payload: ReservationAdditionalChargeResultRequest,
        *,
        correlation_id: str | None = None,
    ) -> ReservationCheckStatusResponse:
        reservation_before = self.reservation_repository.get_by_id(reservation_id)
        if not reservation_before:
            raise ReservationNotFoundError("Reservation not found")
        if reservation_before.status != "modification_pending_payment":
            raise InvalidReservationStatusError(
                "Reservation is not awaiting additional charge callback"
            )

        status_after, action_applied = self._resolve_status_transition(payload.status.value)
        update_kwargs: dict = {
            "status": status_after,
            "expected_version": reservation_before.version,
        }

        if payload.status.value == "succeeded":
            pending_modification = self._find_pending_modification_payload(reservation_id)
            if not pending_modification:
                raise InvalidReservationStatusError(
                    "Pending modification payload not found for callback application"
                )
            try:
                update_kwargs.update(
                    {
                        "check_in_date": self._to_naive_datetime(
                            pending_modification["check_in_date"]
                        ),
                        "check_out_date": self._to_naive_datetime(
                            pending_modification["check_out_date"]
                        ),
                        "number_of_guests": int(pending_modification["number_of_guests"]),
                        "total_price": Decimal(str(pending_modification["total_price"])),
                    }
                )
            except (KeyError, ValueError, TypeError, InvalidOperation) as exc:
                raise InvalidReservationStatusError(
                    f"Invalid pending modification payload: {exc}"
                ) from exc

        updated = self.reservation_repository.apply_updates(reservation_id, **update_kwargs)
        if not updated:
            raise ReservationNotFoundError("Reservation not found")

        self.event_repository.add(
            ReservationEventCreateRequest(
                reservation_id=reservation_id,
                event_type=ReservationEventType.status_changed,
                result=(
                    ReservationEventResult.success
                    if payload.status.value == "succeeded"
                    else ReservationEventResult.failed
                ),
                before_payload=reservation_before.model_dump(mode="json"),
                after_payload={
                    **updated.model_dump(mode="json"),
                    "correlation_id": correlation_id,
                    "callback_type": "additional_charge_result",
                    "callback_status": payload.status.value,
                    "payment_id": str(payload.payment_id) if payload.payment_id else None,
                    "amount_in_cents": payload.amount_in_cents,
                },
            )
        )

        return ReservationCheckStatusResponse(
            reservation=updated,
            status_before=reservation_before.status,
            status_after=updated.status,
            action_applied=action_applied,
        )