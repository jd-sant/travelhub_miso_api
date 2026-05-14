"""Dependency providers for the Inventory service."""
from sqlmodel import Session

from fastapi import Depends

from adapters.repositories import SQLModelPricingManagementRepository
from adapters.repositories import SQLModelSearchRepository
from adapters.services.properties_client import PropertiesOwnershipClient
from adapters.services.properties_service_client import HttpPropertiesServiceClient
from adapters.services.reservations_service_client import HttpReservationsServiceClient
from db.session import get_session
from domain.ports.properties_service import PropertiesServicePort
from domain.ports.reservations_service import ReservationsServicePort
from domain.use_cases import CheckPropertyAvailabilityUseCase, PricingManagementUseCase


def get_properties_client() -> PropertiesServicePort:
    return HttpPropertiesServiceClient()


def get_reservations_client() -> ReservationsServicePort:
    return HttpReservationsServiceClient()


def get_property_availability_use_case(
    session: Session = Depends(get_session),
    properties: PropertiesServicePort = Depends(get_properties_client),
    reservations: ReservationsServicePort = Depends(get_reservations_client),
) -> CheckPropertyAvailabilityUseCase:
    catalog = SQLModelSearchRepository(session)
    return CheckPropertyAvailabilityUseCase(properties, reservations, catalog=catalog)


def get_pricing_management_use_case(
    session: Session = Depends(get_session),
) -> PricingManagementUseCase:
    repository = SQLModelPricingManagementRepository(session)
    ownership_client = PropertiesOwnershipClient()
    return PricingManagementUseCase(repository, ownership_client)
