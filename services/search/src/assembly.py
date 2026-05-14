"""Dependency providers for the Search service (stateless, HTTP-driven)."""
from functools import lru_cache
from typing import Optional

from fastapi import Depends
from redis import Redis

from adapters.cache.redis_cache import RedisCache
from adapters.services.inventory_service_client import HttpInventoryServiceClient
from adapters.services.properties_service_client import HttpPropertiesServiceClient
from adapters.services.reservations_service_client import HttpReservationsServiceClient
from core.config import settings
from db.redis import get_redis_client
from domain.ports.cache_port import CachePort
from domain.ports.inventory_service import InventoryServicePort
from domain.ports.properties_service import PropertiesServicePort
from domain.ports.reservations_service import ReservationsServicePort
from domain.use_cases.check_property_availability import (
    CheckPropertyAvailabilityUseCase,
)
from domain.use_cases.search_properties import SearchPropertiesUseCase


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


@lru_cache
def get_inventory_client() -> InventoryServicePort:
    return HttpInventoryServiceClient()


def get_cache(redis: Optional[Redis] = Depends(get_redis_client)) -> Optional[CachePort]:
    return build_cache(redis)


def get_search_properties_use_case(
    properties: PropertiesServicePort = Depends(get_properties_client),
    reservations: ReservationsServicePort = Depends(get_reservations_client),
    inventory: InventoryServicePort = Depends(get_inventory_client),
    cache: Optional[CachePort] = Depends(get_cache),
) -> SearchPropertiesUseCase:
    return SearchPropertiesUseCase(
        properties,
        reservations,
        cache=cache,
        inventory=inventory,
    )


def get_property_availability_use_case(
    properties: PropertiesServicePort = Depends(get_properties_client),
    reservations: ReservationsServicePort = Depends(get_reservations_client),
    inventory: InventoryServicePort = Depends(get_inventory_client),
) -> CheckPropertyAvailabilityUseCase:
    return CheckPropertyAvailabilityUseCase(properties, reservations, inventory)
