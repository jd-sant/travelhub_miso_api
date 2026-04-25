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
    ReservationRefundResultRequest,
    ReservationStatusUpdateRequest,
)
from domain.ports.reservation_event_repository import ReservationEventRepository
from domain.use_cases.apply_additional_charge_result import (
    ApplyAdditionalChargeResultUseCase,
)
from domain.use_cases.apply_refund_result import ApplyRefundResultUseCase
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


def get_apply_refund_result_use_case(
    repository=Depends(get_reservation_repository),
    event_repository: ReservationEventRepository = Depends(get_reservation_event_repository),
):
    return ApplyRefundResultUseCase(repository, event_repository)


def get_apply_additional_charge_result_use_case(
    repository=Depends(get_reservation_repository),
    event_repository: ReservationEventRepository = Depends(get_reservation_event_repository),
):
    return ApplyAdditionalChargeResultUseCase(repository, event_repository)


def _verify_api_key(x_internal_api_key: str = Header(default=None)) -> None:
    if not x_internal_api_key or not compare_digest(
        x_internal_api_key.strip(), settings.internal_api_key
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden",
        )


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
    use_case: ApplyRefundResultUseCase = Depends(get_apply_refund_result_use_case),
):
    try:
        reservation_uuid = UUID(reservation_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid reservation ID format",
        )

    try:
        return use_case.execute(
            reservation_uuid,
            payload,
            correlation_id=correlation_id,
        )
    except InvalidReservationStatusError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except ReservationConcurrencyError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"message": str(exc), "correlation_id": correlation_id},
        )
    except ReservationNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reservation not found",
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
    use_case: ApplyAdditionalChargeResultUseCase = Depends(
        get_apply_additional_charge_result_use_case
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
        return use_case.execute(
            reservation_uuid,
            payload,
            correlation_id=correlation_id,
        )
    except InvalidReservationStatusError as exc:
        message = str(exc)
        status_code = (
            status.HTTP_409_CONFLICT
            if "Pending modification payload not found" in message
            or "Invalid pending modification payload" in message
            else status.HTTP_400_BAD_REQUEST
        )
        raise HTTPException(status_code=status_code, detail=message)
    except ReservationConcurrencyError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"message": str(exc), "correlation_id": correlation_id},
        )
    except ReservationNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reservation not found",
        )