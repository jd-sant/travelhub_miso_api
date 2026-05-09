"""SearchPropertiesUseCase: stateless orchestrator over properties + reservations."""
import json
import logging
from decimal import Decimal
from typing import Optional

from domain.ports.cache_port import CachePort
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
    ):
        self._properties = properties
        self._reservations = reservations
        self._cache = cache

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
                sort_by=payload.order_by,
                sort_dir=payload.order_dir,
                page=payload.page,
                page_size=payload.page_size,
            )
        )

        property_ids = [item.id for item in page.items]
        availability = self._reservations.availability_check(
            property_ids, payload.check_in, payload.check_out
        )
        available_set = set(availability.available)

        items: list[PropertySearchItem] = []
        for prop in page.items:
            if prop.id not in available_set:
                continue
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
                    price_from=Decimal(str(prop.price_per_night)),
                    currency=prop.currency,
                    amenities=prop.amenities,
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
                q.city.lower(),
                q.check_in.isoformat(),
                q.check_out.isoformat(),
                str(q.guests),
                amenities_part,
                str(q.min_price) if q.min_price is not None else "_",
                str(q.max_price) if q.max_price is not None else "_",
                q.order_by,
                q.order_dir,
                str(q.page),
                str(q.page_size),
            ]
        )
