from functools import lru_cache

from fastapi import Depends, HTTPException, status
from sqlmodel import Session

from adapters.repositories.reservation_repository import SQLModelReservationRepository
from adapters.services.payments_client import PaymentsServiceClient
from adapters.services.properties_client import PropertiesServiceClient
from adapters.services.property_service_client import (
    HttpPropertyServiceClient,
    NoOpPropertyServiceClient,
)
from adapters.services.inventory_pricing_client import (
    HttpInventoryPricingClient,
    NoOpInventoryPricingClient,
)
from domain.ports.property_service_client import PropertyServiceClient
from domain.ports.pricing_service_client import PricingServiceClient
from adapters.services.scheduler_service import (
    EventBridgeReservationScheduler,
    NoOpReservationScheduler,
)
from adapters.services.users_client import UsersServiceClient
from core.config import settings
from db.session import get_session
from domain.ports.reservation_scheduler import ReservationScheduler
from domain.use_cases.check_properties_availability import (
    CheckPropertiesAvailabilityUseCase,
)
from domain.use_cases.check_reservation_status import CheckReservationStatusUseCase
from domain.use_cases.compute_host_metrics import (
    ComputeHostMetricsUseCase,
    ComputeRevenueTrendsUseCase,
)
from domain.use_cases.create_reservation import CreateReservationUseCase
from domain.use_cases.list_host_reservations import ListHostReservationsUseCase
from domain.use_cases.update_reservation import UpdateReservationStatusUseCase


def get_reservation_repository(
    session: Session = Depends(get_session),
) -> SQLModelReservationRepository:
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
            scheduler_group_name=settings.scheduler_group_name,
            delay_minutes=settings.reservation_scheduler_delay_minutes,
        )
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Scheduler configuration error",
        ) from exc


def get_properties_client() -> PropertiesServiceClient:
    return PropertiesServiceClient()


def get_property_service_client() -> PropertyServiceClient:
    if settings.is_test:
        return NoOpPropertyServiceClient()
    return HttpPropertyServiceClient()


def get_pricing_service_client() -> PricingServiceClient:
    if settings.is_test:
        return NoOpInventoryPricingClient()
    return HttpInventoryPricingClient()


def get_users_client() -> UsersServiceClient:
    return UsersServiceClient()


def get_payments_client() -> PaymentsServiceClient:
    return PaymentsServiceClient()


def get_create_reservation_use_case(
    repository: SQLModelReservationRepository = Depends(get_reservation_repository),
    scheduler: ReservationScheduler = Depends(get_reservation_scheduler),
    properties_client: PropertiesServiceClient = Depends(get_properties_client),
    property_client: PropertyServiceClient = Depends(get_property_service_client),
    pricing_client: PricingServiceClient = Depends(get_pricing_service_client),
) -> CreateReservationUseCase:
    return CreateReservationUseCase(
        repository, scheduler, properties_client, property_client, pricing_client
    )


def get_update_reservation_status_use_case(
    repository: SQLModelReservationRepository = Depends(get_reservation_repository),
) -> UpdateReservationStatusUseCase:
    return UpdateReservationStatusUseCase(repository)


def get_check_reservation_status_use_case(
    updater: UpdateReservationStatusUseCase = Depends(
        get_update_reservation_status_use_case
    ),
) -> CheckReservationStatusUseCase:
    return CheckReservationStatusUseCase(updater)


def get_check_properties_availability_use_case(
    repository: SQLModelReservationRepository = Depends(get_reservation_repository),
) -> CheckPropertiesAvailabilityUseCase:
    return CheckPropertiesAvailabilityUseCase(repository)


def get_list_host_reservations_use_case(
    repository: SQLModelReservationRepository = Depends(get_reservation_repository),
    properties_client: PropertiesServiceClient = Depends(get_properties_client),
    users_client: UsersServiceClient = Depends(get_users_client),
) -> ListHostReservationsUseCase:
    return ListHostReservationsUseCase(repository, properties_client, users_client)


def get_compute_host_metrics_use_case(
    repository: SQLModelReservationRepository = Depends(get_reservation_repository),
    properties_client: PropertiesServiceClient = Depends(get_properties_client),
    payments_client: PaymentsServiceClient = Depends(get_payments_client),
) -> ComputeHostMetricsUseCase:
    return ComputeHostMetricsUseCase(repository, properties_client, payments_client)


def get_compute_revenue_trends_use_case(
    repository: SQLModelReservationRepository = Depends(get_reservation_repository),
    properties_client: PropertiesServiceClient = Depends(get_properties_client),
    payments_client: PaymentsServiceClient = Depends(get_payments_client),
) -> ComputeRevenueTrendsUseCase:
    return ComputeRevenueTrendsUseCase(repository, properties_client, payments_client)



