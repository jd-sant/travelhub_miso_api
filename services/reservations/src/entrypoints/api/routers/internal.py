from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlmodel import Session

from adapters.repositories.reservation_event_repository import (
    SQLModelReservationEventRepository,
)
from adapters.repositories.reservation_repository import SQLModelReservationRepository
from core.config import settings
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
from errors import InvalidReservationStatusError, ReservationNotFoundError

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
    if x_internal_api_key != settings.internal_api_key:
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
    return "confirmed", "additional_charge_failed"


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


@router.post(
    "/reservations/{reservation_id}/refund-result",
    response_model=ReservationCheckStatusResponse,
    status_code=status.HTTP_200_OK,
)
def apply_refund_result(
    reservation_id: str,
    payload: ReservationRefundResultRequest,
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

    updated = repository.apply_updates(
        reservation_uuid,
        status=status_after,
        cancelled_at=(
            datetime.now(UTC).replace(tzinfo=None)
            if status_after == "refund_completed"
            else None
        ),
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
    updated = repository.apply_updates(reservation_uuid, status=status_after)
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