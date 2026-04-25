from datetime import datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from adapters.repositories.reservation_repository import SQLModelReservationRepository
from assembly import (
    get_compute_host_metrics_use_case,
    get_compute_revenue_trends_use_case,
    get_create_reservation_use_case,
    get_list_host_reservations_use_case,
    get_reservation_repository,
)
from core.auth import AuthenticatedUser, get_current_hotel_user
from domain.schemas.reservation import (
    HostMetrics,
    HostReservationsPage,
    HostRevenueTrends,
    ReservationCreateRequest,
    ReservationResponse,
    ReservationSummary,
)
from domain.use_cases.compute_host_metrics import (
    ComputeHostMetricsUseCase,
    ComputeRevenueTrendsUseCase,
)
from domain.use_cases.create_reservation import CreateReservationUseCase
from domain.use_cases.list_host_reservations import ListHostReservationsUseCase
from errors import (
    InvalidReservationDateError,
    ReservationSchedulingError,
    RoomNotAvailableError,
    ServiceUnavailableError,
)

router = APIRouter()


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
            hold_expires_at=reservation.hold_expires_at,
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


@router.get("/host/me/metrics", response_model=HostMetrics)
def get_host_metrics(
    start_date: datetime | None = Query(default=None),
    end_date: datetime | None = Query(default=None),
    user: AuthenticatedUser = Depends(get_current_hotel_user),
    use_case: ComputeHostMetricsUseCase = Depends(get_compute_host_metrics_use_case),
):
    try:
        return use_case.execute(
            owner_id=user.id, start_date=start_date, end_date=end_date
        )
    except ServiceUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        )


@router.get("/host/me/revenue-trends", response_model=HostRevenueTrends)
def get_host_revenue_trends(
    start_date: datetime | None = Query(default=None),
    end_date: datetime | None = Query(default=None),
    granularity: Literal["day", "week", "month"] = Query(default="week"),
    user: AuthenticatedUser = Depends(get_current_hotel_user),
    use_case: ComputeRevenueTrendsUseCase = Depends(
        get_compute_revenue_trends_use_case
    ),
):
    try:
        return use_case.execute(
            owner_id=user.id,
            start_date=start_date,
            end_date=end_date,
            granularity=granularity,
        )
    except ServiceUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        )


@router.get("/host/me", response_model=HostReservationsPage)
def list_host_reservations(
    status_param: list[str] | None = Query(default=None, alias="status"),
    start_date: datetime | None = Query(default=None),
    end_date: datetime | None = Query(default=None),
    guest_name: str | None = Query(default=None),
    sort_by: Literal["check_in_date", "created_at", "total_price"] = Query(
        default="check_in_date"
    ),
    sort_dir: Literal["asc", "desc"] = Query(default="desc"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    user: AuthenticatedUser = Depends(get_current_hotel_user),
    use_case: ListHostReservationsUseCase = Depends(get_list_host_reservations_use_case),
):
    """Listado paginado de reservas filtrado por las propiedades del hotel autenticado."""
    try:
        return use_case.execute(
            owner_id=user.id,
            statuses=status_param,
            start_date=start_date,
            end_date=end_date,
            guest_name=guest_name,
            sort_by=sort_by,
            sort_dir=sort_dir,
            page=page,
            page_size=page_size,
        )
    except ServiceUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
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
