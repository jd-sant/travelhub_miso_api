from decimal import Decimal
import logging
from typing import Optional

from sqlalchemy import and_, asc, desc, func
from sqlmodel import Session, select
from pydantic import ValidationError

from adapters.models import Amenity
from adapters.models import InventoryCalendar
from adapters.models import Property
from adapters.models import PropertyAmenity
from adapters.models import RateCalendar
from adapters.models import RatePlan
from adapters.models import RoomType
from domain.ports.cache_port import CachePort
from domain.ports.search_catalog import SearchCatalogPort
from domain.schemas.availability import (
    PropertyAvailabilityQuery,
    PropertyAvailabilityResponse,
)
from domain.schemas.search import PropertySearchItem, SearchQuery, SearchResult

logger = logging.getLogger(__name__)


def _normalize_decimal(value: Decimal | None) -> str:
    if value is None:
        return ""
    return format(value.normalize(), "f")


def _make_cache_key(query: SearchQuery) -> str:
    """Deterministic, normalized cache key from all query parameters."""
    amenities_key = ",".join(sorted({a.strip().lower() for a in query.amenities if a.strip()}))
    return (
        f"search:"
        f"{query.city.strip().lower()}:"
        f"{query.check_in}:{query.check_out}:"
        f"{query.guests}:"
        f"{amenities_key}:"
        f"{_normalize_decimal(query.min_price)}:{_normalize_decimal(query.max_price)}:"
        f"{query.order_by.lower()}:{query.order_dir.lower()}:"
        f"{query.page}:{query.page_size}"
    )


def _make_availability_cache_key(query: PropertyAvailabilityQuery) -> str:
    return (
        f"availability:"
        f"{query.property_id}:"
        f"{query.check_in}:{query.check_out}:"
        f"{query.guests}"
    )


class SQLModelSearchRepository(SearchCatalogPort):
    def __init__(self, session: Session, cache: Optional[CachePort] = None):
        self.session = session
        self._cache = cache

    def search(self, query: SearchQuery) -> SearchResult:
        key = None
        if self._cache is not None:
            key = _make_cache_key(query)
            cached = self._cache.get(key)
            if cached is not None:
                try:
                    return SearchResult.model_validate(cached)
                except ValidationError as exc:
                    logger.warning("Invalid cached search result for %s: %s", key, exc)
                    try:
                        self._cache.delete(key)
                    except Exception as delete_exc:
                        logger.warning("Failed to delete invalid cached search result for %s: %s", key, delete_exc)

        result = self._search_from_db(query)

        if self._cache is not None and key is not None:
            self._cache.set(key, result.model_dump(mode="json"), ttl=self._cache.get_ttl())

        return result

    def check_availability(
        self, query: PropertyAvailabilityQuery
    ) -> PropertyAvailabilityResponse:
        key = None
        if self._cache is not None:
            key = _make_availability_cache_key(query)
            cached = self._cache.get(key)
            if cached is not None:
                try:
                    return PropertyAvailabilityResponse.model_validate(cached)
                except ValidationError as exc:
                    logger.warning("Invalid cached availability result for %s: %s", key, exc)
                    try:
                        self._cache.delete(key)
                    except Exception as delete_exc:
                        logger.warning(
                            "Failed to delete invalid cached availability result for %s: %s",
                            key,
                            delete_exc,
                        )

        result = self._check_availability_from_db(query)

        if self._cache is not None and key is not None:
            self._cache.set(key, result.model_dump(mode="json"), ttl=self._cache.get_ttl())

        return result

    def _search_from_db(self, query: SearchQuery) -> SearchResult:
        nights = (query.check_out - query.check_in).days
        if nights <= 0:
            return SearchResult(
                items=[],
                total=0,
                page=query.page,
                page_size=query.page_size,
            )

        amenities = [a.strip().lower() for a in query.amenities if a.strip()]
        city = query.city.strip().lower()

        available_room_type_subq = (
            select(InventoryCalendar.room_type_id)
            .where(
                and_(
                    InventoryCalendar.date >= query.check_in,
                    InventoryCalendar.date < query.check_out,
                    InventoryCalendar.available_units
                    > InventoryCalendar.blocked_units,
                )
            )
            .group_by(InventoryCalendar.room_type_id)
            .having(func.count(func.distinct(InventoryCalendar.date)) == nights)
        )

        avg_calendar_price_subq = (
            select(func.avg(RateCalendar.price))
            .where(
                and_(
                    RateCalendar.rate_plan_id == RatePlan.id,
                    RateCalendar.date >= query.check_in,
                    RateCalendar.date < query.check_out,
                )
            )
            .correlate(RatePlan)
            .scalar_subquery()
        )

        effective_price_expr = func.coalesce(avg_calendar_price_subq, RatePlan.base_price)
        min_price_expr = func.min(effective_price_expr)

        base_stmt = (
            select(
                Property.id,
                Property.name,
                Property.city,
                Property.country,
                Property.max_capacity,
                Property.main_image_url,
                Property.rating,
                min_price_expr.label("price_from"),
                func.min(RatePlan.currency).label("currency"),
            )
            .join(RoomType, RoomType.property_id == Property.id)
            .join(RatePlan, RatePlan.room_type_id == RoomType.id)
            .where(
                and_(
                    func.lower(Property.city) == city,
                    Property.is_active.is_(True),
                    RoomType.is_active.is_(True),
                    RatePlan.is_active.is_(True),
                    RoomType.capacity >= query.guests,
                    RoomType.id.in_(available_room_type_subq),
                )
            )
        )

        if amenities:
            amenity_match_subq = (
                select(PropertyAmenity.property_id)
                .join(Amenity, Amenity.id == PropertyAmenity.amenity_id)
                .where(func.lower(Amenity.name).in_(amenities))
                .group_by(PropertyAmenity.property_id)
                .having(func.count(func.distinct(func.lower(Amenity.name))) == len(set(amenities)))
            )
            base_stmt = base_stmt.where(Property.id.in_(amenity_match_subq))

        grouped_stmt = base_stmt.group_by(
            Property.id,
            Property.name,
            Property.city,
            Property.country,
            Property.max_capacity,
            Property.main_image_url,
            Property.rating,
        )

        if query.min_price is not None:
            grouped_stmt = grouped_stmt.having(min_price_expr >= query.min_price)
        if query.max_price is not None:
            grouped_stmt = grouped_stmt.having(min_price_expr <= query.max_price)

        total_stmt = select(func.count()).select_from(grouped_stmt.subquery())
        total = self.session.exec(total_stmt).one()

        sort_map = {
            "price": min_price_expr,
            "rating": func.coalesce(Property.rating, 0),
            "name": Property.name,
        }
        sort_expr = sort_map.get(query.order_by.lower(), min_price_expr)
        sort_fn = desc if query.order_dir.lower() == "desc" else asc

        paged_stmt = (
            grouped_stmt.order_by(sort_fn(sort_expr))
            .offset((query.page - 1) * query.page_size)
            .limit(query.page_size)
        )

        rows = self.session.exec(paged_stmt).all()
        property_ids = [row.id for row in rows]

        amenities_by_property: dict = {}
        if property_ids:
            amenity_rows = self.session.exec(
                select(PropertyAmenity.property_id, Amenity.name)
                .join(Amenity, Amenity.id == PropertyAmenity.amenity_id)
                .where(PropertyAmenity.property_id.in_(property_ids))
                .order_by(Amenity.name)
            ).all()
            for property_id, amenity_name in amenity_rows:
                amenities_by_property.setdefault(property_id, []).append(amenity_name)

        items = [
            PropertySearchItem(
                id=row.id,
                name=row.name,
                city=row.city,
                country=row.country,
                max_capacity=row.max_capacity,
                main_image_url=row.main_image_url,
                rating=row.rating,
                price_from=Decimal(str(row.price_from)),
                currency=row.currency,
                amenities=amenities_by_property.get(row.id, []),
            )
            for row in rows
        ]

        return SearchResult(
            items=items,
            total=total,
            page=query.page,
            page_size=query.page_size,
        )

    def _check_availability_from_db(
        self, query: PropertyAvailabilityQuery
    ) -> PropertyAvailabilityResponse:
        nights = (query.check_out - query.check_in).days
        if nights <= 0:
            return PropertyAvailabilityResponse(
                property_id=query.property_id,
                check_in=query.check_in,
                check_out=query.check_out,
                guests=query.guests,
                available=False,
            )

        available_room_type_subq = (
            select(InventoryCalendar.room_type_id)
            .where(
                and_(
                    InventoryCalendar.date >= query.check_in,
                    InventoryCalendar.date < query.check_out,
                    InventoryCalendar.available_units
                    > InventoryCalendar.blocked_units,
                )
            )
            .group_by(InventoryCalendar.room_type_id)
            .having(func.count(func.distinct(InventoryCalendar.date)) == nights)
        )

        avg_calendar_price_subq = (
            select(func.avg(RateCalendar.price))
            .where(
                and_(
                    RateCalendar.rate_plan_id == RatePlan.id,
                    RateCalendar.date >= query.check_in,
                    RateCalendar.date < query.check_out,
                )
            )
            .correlate(RatePlan)
            .scalar_subquery()
        )

        effective_price_expr = func.coalesce(avg_calendar_price_subq, RatePlan.base_price)

        row = self.session.exec(
            select(
                func.min(effective_price_expr).label("price_from"),
                func.min(RatePlan.currency).label("currency"),
            )
            .join(RoomType, RoomType.id == RatePlan.room_type_id)
            .join(Property, Property.id == RoomType.property_id)
            .where(
                and_(
                    Property.id == query.property_id,
                    Property.is_active.is_(True),
                    RoomType.is_active.is_(True),
                    RatePlan.is_active.is_(True),
                    RoomType.capacity >= query.guests,
                    RoomType.id.in_(available_room_type_subq),
                )
            )
        ).first()

        if row is None or row.price_from is None:
            return PropertyAvailabilityResponse(
                property_id=query.property_id,
                check_in=query.check_in,
                check_out=query.check_out,
                guests=query.guests,
                available=False,
            )

        return PropertyAvailabilityResponse(
            property_id=query.property_id,
            check_in=query.check_in,
            check_out=query.check_out,
            guests=query.guests,
            available=True,
            price_from=Decimal(str(row.price_from)),
            currency=row.currency,
        )

