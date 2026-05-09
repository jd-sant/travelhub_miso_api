from datetime import datetime
from functools import lru_cache
from typing import Literal
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from sqlmodel import Session
from adapters.repositories.reservation_command_log_repository import (
    SQLModelReservationCommandLogRepository,
)
from adapters.repositories.reservation_repository import SQLModelReservationRepository
from adapters.repositories.reservation_event_repository import (
    SQLModelReservationEventRepository,
)
from adapters.services.property_service_client import HttpPropertyServiceClient
from adapters.services.search_pricing_client import HttpSearchPricingClient
from adapters.services.payment_service_client import HttpPaymentServiceClient
from adapters.services.scheduler_service import (
    EventBridgeReservationScheduler,
    NoOpReservationScheduler,
)
from assembly import (
    get_compute_host_metrics_use_case,
    get_compute_revenue_trends_use_case,
    get_create_reservation_use_case,
    get_list_host_reservations_use_case,
    get_reservation_repository,
)
from core.auth import AuthenticatedUser, get_current_hotel_user
from core.config import settings
from core.telemetry import resolve_correlation_id
from db.session import get_session
from domain.ports.property_service_client import PropertyServiceClient
from domain.ports.payment_service_client import PaymentServiceClient
from domain.ports.pricing_service_client import PricingServiceClient
from domain.ports.reservation_scheduler import ReservationScheduler
from domain.schemas.reservation import (
    HostMetrics,
    HostReservationsPage,
    HostRevenueTrends,
    ReservationCancellationConfirmRequest,
    ReservationCancellationPreviewResponse,
    ReservationConfirmResponse,
    ReservationCreateRequest,
    ReservationHistoryResponse,
    ReservationModificationConfirmRequest,
    ReservationModificationPreviewRequest,
    ReservationModificationPreviewResponse,
    ReservationResponse,
    ReservationWithDetailsResponse,
    ReservationSummary,
)
from domain.use_cases.compute_host_metrics import (
    ComputeHostMetricsUseCase,
    ComputeRevenueTrendsUseCase,
)
from domain.use_cases.confirm_reservation_cancellation import (
    ConfirmReservationCancellationUseCase,
)
from domain.use_cases.confirm_reservation_modification import (
    ConfirmReservationModificationUseCase,
)
from domain.use_cases.create_reservation import CreateReservationUseCase
from domain.use_cases.list_host_reservations import ListHostReservationsUseCase
from domain.use_cases.get_reservation_history import GetReservationHistoryUseCase
from domain.use_cases.preview_reservation_cancellation import (
    PreviewReservationCancellationUseCase,
)
from domain.use_cases.preview_reservation_modification import (
    PreviewReservationModificationUseCase,
)
from errors import (
    InvalidReservationOperationError,
    InvalidReservationDateError,
    PropertyNotFoundError,
    PropertyServiceUnavailableError,
    PaymentServiceUnavailableError,
    ReservationSchedulingError,
    ReservationNotFoundError,
    ReservationOwnershipError,
    ReservationConcurrencyError,
    RoomNotAvailableError,
    ServiceUnavailableError,
)

router = APIRouter()


def get_reservation_repository(session: Session = Depends(get_session)):
    return SQLModelReservationRepository(session)


def get_reservation_event_repository(session: Session = Depends(get_session)):
    return SQLModelReservationEventRepository(session)


def get_reservation_command_log_repository(session: Session = Depends(get_session)):
    return SQLModelReservationCommandLogRepository(session)


def get_property_service_client() -> PropertyServiceClient:
    return HttpPropertyServiceClient()


def get_payment_service_client() -> PaymentServiceClient:
    return HttpPaymentServiceClient()


def get_pricing_service_client() -> PricingServiceClient:
    return HttpSearchPricingClient()


@lru_cache
def get_reservation_scheduler() -> ReservationScheduler:
    if not settings.reservation_scheduler_enabled or settings.is_local_dev:
        return NoOpReservationScheduler()

    try:
        return EventBridgeReservationScheduler(
            aws_region=settings.aws_region,
            lambda_arn=settings.lambda_arn,
            scheduler_role_arn=settings.scheduler_role_arn,
            api_base_url=settings.api_base_url,
            scheduler_group_name=settings.scheduler_group_name,
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
    property_client: PropertyServiceClient = Depends(get_property_service_client),
    pricing_client: PricingServiceClient = Depends(get_pricing_service_client),
):
    return CreateReservationUseCase(
        repository,
        scheduler,
        properties_client=None,
        property_client=property_client,
        pricing_client=pricing_client,
    )


def get_preview_modification_use_case(
    repository=Depends(get_reservation_repository),
    property_client: PropertyServiceClient = Depends(get_property_service_client),
    pricing_client: PricingServiceClient = Depends(get_pricing_service_client),
    event_repository=Depends(get_reservation_event_repository),
):
    return PreviewReservationModificationUseCase(
        repository,
        property_client,
        event_repository,
        pricing_client,
    )


def get_preview_cancellation_use_case(
    repository=Depends(get_reservation_repository),
    property_client: PropertyServiceClient = Depends(get_property_service_client),
    pricing_client: PricingServiceClient = Depends(get_pricing_service_client),
    event_repository=Depends(get_reservation_event_repository),
):
    return PreviewReservationCancellationUseCase(
        repository,
        property_client,
        event_repository,
        pricing_client,
    )


def get_confirm_modification_use_case(
    repository=Depends(get_reservation_repository),
    event_repository=Depends(get_reservation_event_repository),
    command_log_repository=Depends(get_reservation_command_log_repository),
    payment_client: PaymentServiceClient = Depends(get_payment_service_client),
    preview_use_case: PreviewReservationModificationUseCase = Depends(
        get_preview_modification_use_case
    ),
):
    return ConfirmReservationModificationUseCase(
        repository,
        event_repository,
        command_log_repository,
        payment_client,
        preview_use_case,
    )


def get_confirm_cancellation_use_case(
    repository=Depends(get_reservation_repository),
    event_repository=Depends(get_reservation_event_repository),
    command_log_repository=Depends(get_reservation_command_log_repository),
    payment_client: PaymentServiceClient = Depends(get_payment_service_client),
    preview_use_case: PreviewReservationCancellationUseCase = Depends(
        get_preview_cancellation_use_case
    ),
):
    return ConfirmReservationCancellationUseCase(
        repository,
        event_repository,
        command_log_repository,
        payment_client,
        preview_use_case,
    )


def get_reservation_history_use_case(
    repository=Depends(get_reservation_repository),
    event_repository=Depends(get_reservation_event_repository),
):
    return GetReservationHistoryUseCase(repository, event_repository)


def _get_actor_user_id(x_traveler_id: str = Header(default=None)) -> UUID:
    if not x_traveler_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Traveler-Id header is required",
        )
    try:
        return UUID(x_traveler_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid X-Traveler-Id header format",
        ) from exc


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
    revenue_mode: Literal["confirmed_reservations", "collected_payments"] = Query(default="confirmed_reservations"),
    currency: str | None = Query(default=None),
    user: AuthenticatedUser = Depends(get_current_hotel_user),
    use_case: ComputeHostMetricsUseCase = Depends(get_compute_host_metrics_use_case),
):
    try:
        return use_case.execute(
            owner_id=user.id,
            start_date=start_date,
            end_date=end_date,
            revenue_mode=revenue_mode,
            currency=currency,
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
    revenue_mode: Literal["confirmed_reservations", "collected_payments"] = Query(default="confirmed_reservations"),
    currency: str | None = Query(default=None),
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
            revenue_mode=revenue_mode,
            currency=currency,
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


@router.post(
    "/{reservation_id}/modifications/preview",
    response_model=ReservationModificationPreviewResponse,
    status_code=status.HTTP_200_OK,
)
def preview_reservation_modification(
    reservation_id: str,
    payload: ReservationModificationPreviewRequest,
    use_case: PreviewReservationModificationUseCase = Depends(
        get_preview_modification_use_case
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
        return use_case.execute(reservation_uuid, payload)
    except ReservationNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except PropertyNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except PropertyServiceUnavailableError as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.post(
    "/{reservation_id}/cancellation/preview",
    response_model=ReservationCancellationPreviewResponse,
    status_code=status.HTTP_200_OK,
)
def preview_reservation_cancellation(
    reservation_id: str,
    use_case: PreviewReservationCancellationUseCase = Depends(
        get_preview_cancellation_use_case
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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except PropertyNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except PropertyServiceUnavailableError as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.post(
    "/{reservation_id}/modifications/confirm",
    response_model=ReservationConfirmResponse,
    status_code=status.HTTP_200_OK,
)
def confirm_reservation_modification(
    reservation_id: str,
    payload: ReservationModificationConfirmRequest,
    request: Request,
    correlation_id: str = Depends(resolve_correlation_id),
    actor_user_id: UUID = Depends(_get_actor_user_id),
    use_case: ConfirmReservationModificationUseCase = Depends(
        get_confirm_modification_use_case
    ),
):
    try:
        reservation_uuid = UUID(reservation_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid reservation ID format",
        )

    source_ip = request.client.host if request.client else None
    try:
        return use_case.execute(
            reservation_uuid,
            payload,
            actor_user_id=actor_user_id,
            source_ip=source_ip,
            correlation_id=correlation_id,
        )
    except ReservationNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ReservationOwnershipError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except InvalidReservationOperationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except PropertyNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except PropertyServiceUnavailableError as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e))
    except PaymentServiceUnavailableError as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e))
    except ReservationConcurrencyError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"message": str(e), "correlation_id": correlation_id},
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.post(
    "/{reservation_id}/cancellation/confirm",
    response_model=ReservationConfirmResponse,
    status_code=status.HTTP_200_OK,
)
def confirm_reservation_cancellation(
    reservation_id: str,
    payload: ReservationCancellationConfirmRequest,
    request: Request,
    correlation_id: str = Depends(resolve_correlation_id),
    actor_user_id: UUID = Depends(_get_actor_user_id),
    use_case: ConfirmReservationCancellationUseCase = Depends(
        get_confirm_cancellation_use_case
    ),
):
    try:
        reservation_uuid = UUID(reservation_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid reservation ID format",
        )

    source_ip = request.client.host if request.client else None
    try:
        return use_case.execute(
            reservation_uuid,
            payload,
            actor_user_id=actor_user_id,
            source_ip=source_ip,
            correlation_id=correlation_id,
        )
    except ReservationNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ReservationOwnershipError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except InvalidReservationOperationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except PropertyNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except PropertyServiceUnavailableError as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e))
    except PaymentServiceUnavailableError as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e))
    except ReservationConcurrencyError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"message": str(e), "correlation_id": correlation_id},
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.get(
    "/{reservation_id}/history",
    response_model=ReservationHistoryResponse,
    status_code=status.HTTP_200_OK,
)
def get_reservation_history(
    reservation_id: str,
    actor_user_id: UUID = Depends(_get_actor_user_id),
    use_case: GetReservationHistoryUseCase = Depends(get_reservation_history_use_case),
):
    try:
        reservation_uuid = UUID(reservation_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid reservation ID format",
        )

    try:
        return use_case.execute(reservation_uuid, actor_user_id=actor_user_id)
    except ReservationNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ReservationOwnershipError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))


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


@router.get(
    "/users/{user_id}",
    response_model=list[ReservationWithDetailsResponse],
    status_code=status.HTTP_200_OK,
)
def get_reservations_by_user(
    user_id: str,
    status_group: Optional[str] = Query(
        default=None,
        description="Filter group: 'active', 'past', or 'cancelled'",
        pattern="^(active|past|cancelled)$",
    ),
    repository: SQLModelReservationRepository = Depends(get_reservation_repository),
    property_client: PropertyServiceClient = Depends(get_property_service_client),
):
    try:
        user_uuid = UUID(user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID format",
        )

    reservations = repository.list_by_traveler(user_uuid, status_group=status_group)

    # Enrich with property data (best-effort: failures silently ignored)
    property_cache: dict[UUID, object] = {}
    result = []
    for reservation in reservations:
        prop_id = reservation.id_property
        if prop_id not in property_cache:
            try:
                property_cache[prop_id] = property_client.get_property(prop_id)
            except Exception:
                property_cache[prop_id] = None
        prop = property_cache[prop_id]
        result.append(
            ReservationWithDetailsResponse(
                id=reservation.id,
                reservation=reservation,
                property_name=prop.name if prop else None,
                property_cover_image_url=prop.cover_image_url if prop else None,
            )
        )
    return result
