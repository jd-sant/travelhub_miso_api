from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlmodel import Session

from core.config import settings
from db.session import get_session
from domain.schemas.reservation import (
    ReservationCheckStatusResponse,
    ReservationStatusUpdateRequest,
)
from domain.use_cases.update_reservation import UpdateReservationStatusUseCase
from errors import ReservationNotFoundError
from adapters.repositories.reservation_repository import SQLModelReservationRepository

router = APIRouter(prefix="/internal", tags=["internal"])


def get_reservation_repository(session: Session = Depends(get_session)):
    return SQLModelReservationRepository(session)


def get_update_reservation_status_use_case(
    repository=Depends(get_reservation_repository),
):
    return UpdateReservationStatusUseCase(repository)


def _verify_api_key(x_internal_api_key: str = Header(default=None)) -> None:
    if x_internal_api_key != settings.internal_api_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden",
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
    from uuid import UUID

    try:
        reservation_uuid = UUID(reservation_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid reservation ID format",
        )

    try:
        return use_case.execute(reservation_uuid, payload.status)
    except ReservationNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )