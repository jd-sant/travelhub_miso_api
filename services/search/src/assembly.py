"""Dependency providers for the Search service."""
from functools import lru_cache
from typing import Optional

from fastapi import Depends
from redis import Redis
from sqlmodel import Session

from adapters.cache.redis_cache import RedisCache
from adapters.repositories import SQLModelPricingManagementRepository
from adapters.repositories import SQLModelSearchRepository
from adapters.services.properties_client import PropertiesOwnershipClient
from adapters.services.properties_service_client import HttpPropertiesServiceClient
from adapters.services.reservations_service_client import HttpReservationsServiceClient
from core.config import settings
from db.redis import get_redis_client
from db.session import get_session
from domain.ports.cache_port import CachePort
from domain.ports.properties_service import PropertiesServicePort
from domain.ports.reservations_service import ReservationsServicePort
from domain.use_cases import (
    CheckPropertyAvailabilityUseCase,
    PricingManagementUseCase,
    SearchPropertiesUseCase,
)


def build_cache(redis_client: Optional[Redis]) -> Optional[CachePort]:
    if redis_client is None:
        return None
    return RedisCache(client=redis_client, ttl=settings.redis_cache_ttl_seconds)


@lru_cache
def get_properties_client() -> PropertiesServicePort:
    return HttpPropertiesServiceClient()


@lru_cache
def get_reservations_client() -> ReservationsServicePort:
    return HttpReservationsServiceClient()


def get_cache(redis: Optional[Redis] = Depends(get_redis_client)) -> Optional[CachePort]:
    return build_cache(redis)


def get_search_properties_use_case(
    session: Session = Depends(get_session),
    properties: PropertiesServicePort = Depends(get_properties_client),
    reservations: ReservationsServicePort = Depends(get_reservations_client),
    cache: Optional[CachePort] = Depends(get_cache),
) -> SearchPropertiesUseCase:
    catalog = None if settings.is_test else SQLModelSearchRepository(session, cache)
    return SearchPropertiesUseCase(properties, reservations, cache, catalog=catalog)


def get_property_availability_use_case(
    session: Session = Depends(get_session),
    properties: PropertiesServicePort = Depends(get_properties_client),
    reservations: ReservationsServicePort = Depends(get_reservations_client),
) -> CheckPropertyAvailabilityUseCase:
    catalog = None if settings.is_test else SQLModelSearchRepository(session)
    return CheckPropertyAvailabilityUseCase(properties, reservations, catalog=catalog)


def get_pricing_management_use_case(
    session: Session = Depends(get_session),
) -> PricingManagementUseCase:
    repository = SQLModelPricingManagementRepository(session)
    ownership_client = PropertiesOwnershipClient()
    return PricingManagementUseCase(repository, ownership_client)
