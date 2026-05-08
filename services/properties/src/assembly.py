from typing import Optional

from fastapi import Depends
from redis import Redis
from sqlmodel import Session

from adapters.cache.redis_cache import RedisCache
from adapters.repositories.cached_property_repository import CachedPropertyRepository
from adapters.repositories.property_repository import (
    SQLModelPropertyRepository,
)
from core.config import settings
from db.session import get_session
from db.redis import get_redis_client
from domain.ports.cache_port import CachePort
from domain.ports.property_repository import PropertyRepository
from domain.use_cases.get_property_cancellation_policy import (
    GetPropertyCancellationPolicyUseCase,
)
from domain.use_cases.get_property_detail import (
    GetPropertyDetailUseCase,
)
from domain.use_cases.get_properties_list import (
    GetPropertiesListUseCase,
)
from domain.use_cases.search_properties import SearchPropertiesUseCase


def build_cache(redis_client: Optional[Redis]) -> Optional[CachePort]:
    """Return a CachePort backed by Redis, or None if unavailable."""
    if redis_client is None:
        return None
    return RedisCache(client=redis_client, ttl=settings.redis_cache_ttl_seconds)


def get_property_repository(
    session: Session = Depends(get_session),
) -> PropertyRepository:
    repository = SQLModelPropertyRepository(session)
    cache = build_cache(get_redis_client())
    return CachedPropertyRepository(repository, cache)


def get_property_detail_use_case(
    repository: PropertyRepository = Depends(get_property_repository),
) -> GetPropertyDetailUseCase:
    return GetPropertyDetailUseCase(repository)


def get_properties_list_use_case(
    repository: PropertyRepository = Depends(get_property_repository),
) -> GetPropertiesListUseCase:
    return GetPropertiesListUseCase(repository)


def search_properties_use_case(
    repository: PropertyRepository = Depends(get_property_repository),
) -> SearchPropertiesUseCase:
    return SearchPropertiesUseCase(repository)


def get_property_cancellation_policy_use_case(
    repository: PropertyRepository = Depends(get_property_repository),
) -> GetPropertyCancellationPolicyUseCase:
    return GetPropertyCancellationPolicyUseCase(repository)
