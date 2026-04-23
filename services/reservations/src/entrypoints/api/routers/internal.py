from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from hmac import compare_digest
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlmodel import Session

from adapters.repositories.reservation_event_repository import (
    SQLModelReservationEventRepository,
)
from adapters.repositories.reservation_repository import SQLModelReservationRepository
from core.config import settings
from core.telemetry import resolve_correlation_id
from db.session import get_session
from domain.schemas.reservation import (
    ReservationAdditionalChargeResultRequest,
    ReservationCheckStatusResponse,
    ReservationEventCreateRequest,
    ReservationEventResult,
    ReservationEventType,
    ReservationRefundResultRequest,
    ReservationStatusUpdateRequest,
)
from domain.ports.reservation_event_repository import ReservationEventRepository
from domain.use_cases.check_reservation_status import CheckReservationStatusUseCase
from domain.use_cases.update_reservation import UpdateReservationStatusUseCase
from errors import (
    InvalidReservationStatusError,
    ReservationConcurrencyError,
    ReservationNotFoundError,
)

router = APIRouter(prefix="/internal", tags=["internal"])


def get_reservation_repository(session: Session = Depends(get_session)):
    return SQLModelReservationRepository(session)


def get_reservation_event_repository(session: Session = Depends(get_session)):
    return SQLModelReservationEventRepository(session)


def get_update_reservation_status_use_case(
    repository=Depends(get_reservation_repository),
):
    return UpdateReservationStatusUseCase(repository)


def get_check_reservation_status_use_case(
    updater=Depends(get_update_reservation_status_use_case),
):
    return CheckReservationStatusUseCase(updater)


def _verify_api_key(x_internal_api_key: str = Header(default=None)) -> None:
    if not x_internal_api_key or not compare_digest(
        x_internal_api_key.strip(), settings.internal_api_key
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden",
        )


def _resolve_refund_status_transition(
    current_status: str,
    callback_status: str,
) -> tuple[str, str]:
    if callback_status == "succeeded":
        if current_status == "cancel_requested":
            return "refund_completed", "refund_completed"
        if current_status == "refund_pending":
            return "modification_confirmed", "modification_refund_completed"
        raise InvalidReservationStatusError(
            "Current reservation status does not accept refund success callback"
        )

    return "refund_failed", "refund_failed"


def _resolve_additional_charge_status_transition(callback_status: str) -> tuple[str, str]:
    if callback_status == "succeeded":
        return "modification_confirmed", "additional_charge_completed"
    return "additional_charge_failed", "additional_charge_failed"


def _to_naive_datetime(value: object) -> datetime:
    if isinstance(value, datetime):
        return value.replace(tzinfo=None) if value.tzinfo is not None else value
    if isinstance(value, str):
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.replace(tzinfo=None) if parsed.tzinfo is not None else parsed
    raise ValueError("Invalid datetime value")


def _find_pending_modification_payload(
    reservation_id: UUID,
    event_repository: ReservationEventRepository,
) -> dict | None:
    events = event_repository.list_by_reservation(reservation_id)
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


@router.post(
    "/reservations/{reservation_id}/checkstatus",
    response_model=ReservationCheckStatusResponse,
    status_code=status.HTTP_200_OK,
)
def check_reservation_status(
    reservation_id: str,
    _: None = Depends(_verify_api_key),
    use_case: CheckReservationStatusUseCase = Depends(
        get_check_reservation_status_use_case
    ),
):
    try:
        reservation_uuid = UUID(reservation_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid reservation ID format",
        )

    try:
        return use_case.execute(reservation_uuid)
    except ReservationNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.patch(
    "/reservations/{reservation_id}/status",
    response_model=ReservationCheckStatusResponse,
    status_code=status.HTTP_200_OK,
)
def update_reservation_status(
    reservation_id: str,
    payload: ReservationStatusUpdateRequest,
    correlation_id: str = Depends(resolve_correlation_id),
    _: None = Depends(_verify_api_key),
    use_case: UpdateReservationStatusUseCase = Depends(
        get_update_reservation_status_use_case
    ),
):
    try:
        reservation_uuid = UUID(reservation_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid reservation ID format",
        )

    try:
        return use_case.execute(reservation_uuid, payload.status)
    except InvalidReservationStatusError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except ReservationNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except ReservationConcurrencyError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"message": str(e), "correlation_id": correlation_id},
        )


@router.post(
    "/reservations/{reservation_id}/refund-result",
    response_model=ReservationCheckStatusResponse,
    status_code=status.HTTP_200_OK,
)
def apply_refund_result(
    reservation_id: str,
    payload: ReservationRefundResultRequest,
    correlation_id: str = Depends(resolve_correlation_id),
    _: None = Depends(_verify_api_key),
    repository=Depends(get_reservation_repository),
    event_repository: ReservationEventRepository = Depends(get_reservation_event_repository),
):
    try:
        reservation_uuid = UUID(reservation_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid reservation ID format",
        )

    reservation_before = repository.get_by_id(reservation_uuid)
    if not reservation_before:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reservation not found",
        )

    try:
        status_after, action_applied = _resolve_refund_status_transition(
            reservation_before.status,
            payload.status.value,
        )
    except InvalidReservationStatusError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    try:
        updated = repository.apply_updates(
            reservation_uuid,
            status=status_after,
            expected_version=reservation_before.version,
            cancelled_at=(
                datetime.now(UTC).replace(tzinfo=None)
                if status_after == "refund_completed"
                else None
            ),
        )
    except ReservationConcurrencyError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"message": str(exc), "correlation_id": correlation_id},
        )
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reservation not found",
        )

    event_repository.add(
        ReservationEventCreateRequest(
            reservation_id=reservation_uuid,
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
                "callback_type": "refund_result",
                "callback_status": payload.status.value,
                "refund_id": str(payload.refund_id) if payload.refund_id else None,
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


@router.post(
    "/reservations/{reservation_id}/additional-charge-result",
    response_model=ReservationCheckStatusResponse,
    status_code=status.HTTP_200_OK,
)
def apply_additional_charge_result(
    reservation_id: str,
    payload: ReservationAdditionalChargeResultRequest,
    correlation_id: str = Depends(resolve_correlation_id),
    _: None = Depends(_verify_api_key),
    repository=Depends(get_reservation_repository),
    event_repository: ReservationEventRepository = Depends(get_reservation_event_repository),
):
    try:
        reservation_uuid = UUID(reservation_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid reservation ID format",
        )

    reservation_before = repository.get_by_id(reservation_uuid)
    if not reservation_before:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reservation not found",
        )

    if reservation_before.status != "modification_pending_payment":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reservation is not awaiting additional charge callback",
        )

    status_after, action_applied = _resolve_additional_charge_status_transition(
        payload.status.value
    )

    update_kwargs: dict = {
        "status": status_after,
        "expected_version": reservation_before.version,
    }

    if payload.status.value == "succeeded":
        pending_modification = _find_pending_modification_payload(
            reservation_uuid,
            event_repository,
        )
        if not pending_modification:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Pending modification payload not found for callback application",
            )
        try:
            update_kwargs.update(
                {
                    "check_in_date": _to_naive_datetime(
                        pending_modification["check_in_date"]
                    ),
                    "check_out_date": _to_naive_datetime(
                        pending_modification["check_out_date"]
                    ),
                    "number_of_guests": int(pending_modification["number_of_guests"]),
                    "total_price": Decimal(str(pending_modification["total_price"])),
                }
            )
        except (KeyError, ValueError, TypeError, InvalidOperation) as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Invalid pending modification payload: {exc}",
            )

    try:
        updated = repository.apply_updates(reservation_uuid, **update_kwargs)
    except ReservationConcurrencyError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"message": str(exc), "correlation_id": correlation_id},
        )
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reservation not found",
        )

    event_repository.add(
        ReservationEventCreateRequest(
            reservation_id=reservation_uuid,
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