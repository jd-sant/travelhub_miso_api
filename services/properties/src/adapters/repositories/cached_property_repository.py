from typing import Optional
from uuid import UUID

from pydantic import TypeAdapter, ValidationError

from domain.ports.cache_port import CachePort
from domain.ports.property_repository import PropertyRepository
from domain.schemas.property import (
    PropertyFilters,
    PropertyListResponse,
    PropertyResponse,
    PropertySearchResponse,
)
from domain.schemas.property_policy import PropertyCancellationPolicyResponse

_LIST_ADAPTER = TypeAdapter(list[PropertyListResponse])


class CachedPropertyRepository(PropertyRepository):
    def __init__(self, repository: PropertyRepository, cache: Optional[CachePort] = None):
        self._repository = repository
        self._cache = cache

    def get_by_id(
        self,
        property_id: UUID,
        check_in=None,  # date | None
        check_out=None,  # date | None
    ) -> Optional[PropertyResponse]:
        
        if check_in is not None or check_out is not None:
            return self._repository.get_by_id(property_id, check_in, check_out)

        key = f"properties:detail:{property_id}"
        cached = self._get_cached(key, PropertyResponse)
        if cached is not None:
            return cached

        result = self._repository.get_by_id(property_id)
        if result is not None:
            self._cache_value(key, result.model_dump(mode="json"))
        return result

    def list_all(self, owner_id: UUID | None = None) -> list[PropertyListResponse]:
        owner_key = str(owner_id) if owner_id is not None else "all"
        key = f"properties:list:{owner_key}"
        cached = self._get_cached_list(key)
        if cached is not None:
            return cached

        result = self._repository.list_all(owner_id=owner_id)
        self._cache_value(key, [item.model_dump(mode="json") for item in result])
        return result

    def search(self, filters: PropertyFilters) -> PropertySearchResponse:
        return self._repository.search(filters)

    def get_cancellation_policy(
        self, property_id: UUID
    ) -> Optional[PropertyCancellationPolicyResponse]:
        key = f"properties:policy:{property_id}"
        cached = self._get_cached(key, PropertyCancellationPolicyResponse)
        if cached is not None:
            return cached

        result = self._repository.get_cancellation_policy(property_id)
        if result is not None:
            self._cache_value(key, result.model_dump(mode="json"))
        return result

    def _get_cached(self, key: str, schema):
        if self._cache is None:
            return None
        payload = self._cache.get(key)
        if payload is None:
            return None
        try:
            return schema.model_validate(payload)
        except ValidationError:
            self._cache.delete(key)
            return None

    def _get_cached_list(self, key: str) -> Optional[list[PropertyListResponse]]:
        if self._cache is None:
            return None
        payload = self._cache.get(key)
        if payload is None:
            return None
        try:
            return _LIST_ADAPTER.validate_python(payload)
        except ValidationError:
            self._cache.delete(key)
            return None

    def _cache_value(self, key: str, value: dict | list) -> None:
        if self._cache is None:
            return
        self._cache.set(key, value, ttl=self._cache.get_ttl())

    def invalidate_property_caches(self, property_id: UUID) -> None:
        """Invalidate all caches related to a property (used when pricing is updated)."""
        if self._cache is None:
            return
        # Invalidate detail cache
        self._cache.delete(f"properties:detail:{property_id}")
        # Invalidate list cache (all owners)
        self._cache.delete(f"properties:list:all")
        # Note: Full pattern deletion requires cache.pattern_delete(), 
        # which depends on cache backend (Redis supports it, in-memory doesn't).
        # For in-memory cache, we invalidate the most likely patterns above.
