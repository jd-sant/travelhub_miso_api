"""Dependency providers for the Search service."""
from typing import Optional

from redis import Redis
from sqlmodel import Session

from adapters.cache.redis_cache import RedisCache
from adapters.repositories import SQLModelSearchRepository
from core.config import settings
from domain.ports.cache_port import CachePort
from domain.use_cases import (
    CheckPropertyAvailabilityUseCase,
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
