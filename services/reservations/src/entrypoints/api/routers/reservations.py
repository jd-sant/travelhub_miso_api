from functools import lru_cache
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from adapters.repositories.reservation_repository import SQLModelReservationRepository
from adapters.services.scheduler_service import (
    EventBridgeReservationScheduler,
    NoOpReservationScheduler,
)
from core.config import settings
from db.session import get_session
from domain.ports.reservation_scheduler import ReservationScheduler
from domain.schemas.reservation import ReservationCreateRequest, ReservationResponse, ReservationSummary
from domain.use_cases.create_reservation import CreateReservationUseCase
from errors import (
    InvalidReservationDateError,
    ReservationSchedulingError,
    RoomNotAvailableError,
)

router = APIRouter()


def get_reservation_repository(session: Session = Depends(get_session)):
    return SQLModelReservationRepository(session)


@lru_cache
def get_reservation_scheduler() -> ReservationScheduler:
    if not settings.reservation_scheduler_enabled:
        return NoOpReservationScheduler()

    try:
        return EventBridgeReservationScheduler(
            aws_region=settings.aws_region,
            lambda_arn=settings.lambda_arn,
            scheduler_role_arn=settings.scheduler_role_arn,
            api_base_url=settings.api_base_url,
            delay_minutes=settings.reservation_scheduler_delay_minutes,
        )
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Scheduler configuration error",
        ) from exc


def get_create_reservation_use_case(
    repository=Depends(get_reservation_repository),
    scheduler: ReservationScheduler = Depends(get_reservation_scheduler),
):
    return CreateReservationUseCase(repository, scheduler)


@router.post(
    "",
    response_model=ReservationSummary,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"description": "Invalid reservation data or room not available"},
        500: {"description": "Internal server error"},
    },
)
def create_reservation(
    payload: ReservationCreateRequest,
    use_case: CreateReservationUseCase = Depends(get_create_reservation_use_case),
):
    """
    Create a new reservation for an authenticated traveler.

    Returns reservation summary with calculated total price including taxes.
    """
    try:
        reservation = use_case.execute(payload)
        return ReservationSummary(
            id=reservation.id,
            status=reservation.status,
            total_price=reservation.total_price,
            currency=reservation.currency,
            check_in_date=reservation.check_in_date,
            check_out_date=reservation.check_out_date,
            created_at=reservation.created_at,
        )
    except RoomNotAvailableError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except InvalidReservationDateError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except ReservationSchedulingError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.get("/{reservation_id}", response_model=ReservationResponse)
def get_reservation(
    reservation_id: str,
    repository: SQLModelReservationRepository = Depends(get_reservation_repository),
):
    """
    Get a specific reservation by ID.
    """
    try:
        reservation_uuid = UUID(reservation_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid reservation ID format",
        )

    reservation = repository.get_by_id(reservation_uuid)
    if not reservation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reservation not found",
        )
    return reservation
