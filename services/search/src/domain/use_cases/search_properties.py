"""SearchPropertiesUseCase: stateless orchestrator over properties + reservations."""
import json
import logging
from decimal import Decimal
from typing import Optional
from uuid import UUID

from domain.ports.cache_port import CachePort
from domain.ports.inventory_service import InventoryServicePort
from domain.ports.properties_service import PropertiesServicePort, PropertyQuery
from domain.ports.reservations_service import ReservationsServicePort
from domain.schemas.search import (
    PropertySearchItem,
    SearchQuery,
    SearchResult,
)
from domain.use_cases.base import BaseUseCase

logger = logging.getLogger(__name__)


class SearchPropertiesUseCase(BaseUseCase[SearchQuery, SearchResult]):
    def __init__(
        self,
        properties: PropertiesServicePort,
        reservations: ReservationsServicePort,
        cache: Optional[CachePort] = None,
        inventory: InventoryServicePort | None = None,
    ):
        self._properties = properties
        self._reservations = reservations
        self._cache = cache
        self._inventory = inventory

    def execute(self, payload: SearchQuery) -> SearchResult:
        cache_key = self._cache_key(payload)
        if self._cache is not None:
            cached = self._cache.get(cache_key)
            if cached is not None:
                try:
                    return SearchResult(**cached)
                except Exception as exc:  # noqa: BLE001 - malformed cache, fall through
                    logger.warning("malformed cache for %s: %s", cache_key, exc)
                    self._cache.delete(cache_key)

        page = self._properties.search(
            PropertyQuery(
                city=payload.city,
                min_price=payload.min_price,
                max_price=payload.max_price,
                min_guests=payload.guests,
                amenities=payload.amenities,
                min_lat=payload.min_lat,
                max_lat=payload.max_lat,
                min_lng=payload.min_lng,
                max_lng=payload.max_lng,
                sort_by=payload.order_by,
                sort_dir=payload.order_dir,
                page=payload.page,
                page_size=payload.page_size,
            )
        )

        if payload.check_in is not None and payload.check_out is not None:
            property_ids = [item.id for item in page.items]
            availability = self._reservations.availability_check(
                property_ids, payload.check_in, payload.check_out
            )
            available_set: set[UUID] | None = set(availability.available)
        else:
            available_set = None

        items: list[PropertySearchItem] = []
        for prop in page.items:
            if available_set is not None and prop.id not in available_set:
                continue
            effective_price = Decimal(str(prop.price_per_night))
            effective_currency = prop.currency
            if (
                self._inventory is not None
                and payload.check_in is not None
                and payload.check_out is not None
            ):
                availability_detail = self._inventory.get_availability(
                    prop.id,
                    payload.check_in,
                    payload.check_out,
                    payload.guests,
                )
                if not availability_detail.available:
                    continue
                if availability_detail.price_from is not None:
                    effective_price = availability_detail.price_from
                if availability_detail.currency:
                    effective_currency = availability_detail.currency
            city, country = prop.split_location()
            items.append(
                PropertySearchItem(
                    id=prop.id,
                    name=prop.name,
                    city=city,
                    country=country,
                    max_capacity=prop.max_guests,
                    main_image_url=prop.cover_image_url(),
                    rating=prop.rating,
                    price_from=effective_price,
                    currency=effective_currency,
                    amenities=prop.amenities,
                    latitude=getattr(prop, "latitude", None),
                    longitude=getattr(prop, "longitude", None),
                )
            )

        result = SearchResult(
            items=items,
            total=page.total,
            page=page.page,
            page_size=page.page_size,
        )

        if self._cache is not None:
            self._cache.set(
                cache_key, result.model_dump(mode="json"), self._cache.get_ttl()
            )
        return result

    @staticmethod
    def _cache_key(q: SearchQuery) -> str:
        amenities_part = ",".join(sorted(a.lower() for a in q.amenities)) if q.amenities else "_"
        return ":".join(
            [
                "search",
                q.city.lower() if q.city else "_",
                q.check_in.isoformat() if q.check_in else "_",
                q.check_out.isoformat() if q.check_out else "_",
                str(q.guests),
                amenities_part,
                str(q.min_price) if q.min_price is not None else "_",
                str(q.max_price) if q.max_price is not None else "_",
                f"{q.min_lat:.5f}" if q.min_lat is not None else "_",
                f"{q.max_lat:.5f}" if q.max_lat is not None else "_",
                f"{q.min_lng:.5f}" if q.min_lng is not None else "_",
                f"{q.max_lng:.5f}" if q.max_lng is not None else "_",
                q.order_by,
                q.order_dir,
                str(q.page),
                str(q.page_size),
            ]
        )
