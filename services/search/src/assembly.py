"""Dependency providers for the Search service."""
from typing import Optional

from fastapi import Depends
from redis import Redis
from sqlmodel import Session

from adapters.cache.redis_cache import RedisCache
from adapters.repositories import SQLModelPricingManagementRepository, SQLModelSearchRepository
from adapters.services.properties_client import PropertiesOwnershipClient
from core.config import settings
from db.session import get_session
from domain.ports.cache_port import CachePort
from domain.use_cases import (
    CheckPropertyAvailabilityUseCase,
    PricingManagementUseCase,
    SearchPropertiesUseCase,
)


def build_cache(redis_client: Optional[Redis]) -> Optional[CachePort]:
    """Returns a CachePort backed by Redis, or None if Redis is unavailable."""
    if redis_client is None:
        return None
    return RedisCache(client=redis_client, ttl=settings.redis_cache_ttl_seconds)


def get_search_repository(
    session: Session,
    cache: Optional[CachePort] = None,
) -> SQLModelSearchRepository:
    return SQLModelSearchRepository(session, cache)


def get_search_properties_use_case(
    session: Session,
    cache: Optional[CachePort] = None,
) -> SearchPropertiesUseCase:
    repository = get_search_repository(session, cache)
    return SearchPropertiesUseCase(repository)


def get_property_availability_use_case(
    session: Session,
    cache: Optional[CachePort] = None,
) -> CheckPropertyAvailabilityUseCase:
    repository = get_search_repository(session, cache)
    return CheckPropertyAvailabilityUseCase(repository)


def get_pricing_management_use_case(
    session: Session = Depends(get_session),
) -> PricingManagementUseCase:
    repository = SQLModelPricingManagementRepository(session)
    ownership_client = PropertiesOwnershipClient()
    return PricingManagementUseCase(repository, ownership_client)
