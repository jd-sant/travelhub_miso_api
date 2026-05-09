"""Shared fixtures for the stateless search service tests."""
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Iterable
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from domain.ports.properties_service import PropertiesServicePort, PropertyQuery
from domain.ports.reservations_service import ReservationsServicePort
from domain.schemas.external import (
    AvailabilityResult,
    PropertiesPage,
    PropertyImage,
    PropertyMetadata,
)


@pytest.fixture(scope="session", autouse=True)
def search_test_environment():
    patch = pytest.MonkeyPatch()
    patch.setenv("ENV", "test")
    patch.setenv("APP_ENV", "test")
    patch.setenv("REDIS_CACHE_ENABLED", "false")
    patch.setenv("PROPERTIES_SERVICE_URL", "http://properties-test")
    patch.setenv("RESERVATIONS_SERVICE_URL", "http://reservations-test")
    patch.setenv("INTERNAL_API_KEY", "test-internal-key")
    yield
    patch.undo()


# ── Fakes ──────────────────────────────────────────────────────────────────────


@dataclass
class FakePropertiesServiceClient(PropertiesServicePort):
    """In-memory fake of the properties service."""

    catalog: list[PropertyMetadata] = field(default_factory=list)
    last_query: PropertyQuery | None = None
    raises: Exception | None = None

    def search(self, query: PropertyQuery) -> PropertiesPage:
        self.last_query = query
        if self.raises is not None:
            raise self.raises
        items = self._filter(query)
        total = len(items)
        offset = (query.page - 1) * query.page_size
        page_items = items[offset : offset + query.page_size]
        total_pages = (total + query.page_size - 1) // query.page_size if total else 0
        return PropertiesPage(
            items=page_items,
            total=total,
            page=query.page,
            page_size=query.page_size,
            total_pages=total_pages,
        )

    def get_by_id(self, property_id: UUID) -> PropertyMetadata | None:
        if self.raises is not None:
            raise self.raises
        for item in self.catalog:
            if item.id == property_id:
                return item
        return None

    def _filter(self, query: PropertyQuery) -> list[PropertyMetadata]:
        items = list(self.catalog)
        if query.city:
            needle = query.city.lower()
            items = [it for it in items if needle in it.location.lower()]
        if query.min_price is not None:
            items = [it for it in items if it.price_per_night >= query.min_price]
        if query.max_price is not None:
            items = [it for it in items if it.price_per_night <= query.max_price]
        if query.min_guests is not None:
            items = [it for it in items if it.max_guests >= query.min_guests]
        for amenity in query.amenities:
            needle = amenity.lower()
            items = [
                it
                for it in items
                if any(needle in (a or "").lower() for a in it.amenities)
            ]
        if query.ids:
            id_set = set(query.ids)
            items = [it for it in items if it.id in id_set]
        items = [it for it in items if it.status == 1]
        reverse = query.sort_dir == "desc"
        if query.sort_by == "price":
            items.sort(key=lambda it: it.price_per_night, reverse=reverse)
        elif query.sort_by == "rating":
            items.sort(key=lambda it: it.rating, reverse=reverse)
        elif query.sort_by == "name":
            items.sort(key=lambda it: it.name.lower(), reverse=reverse)
        return items


@dataclass
class FakeReservationsServiceClient(ReservationsServicePort):
    """In-memory fake of the reservations service availability endpoint."""

    blocked_ids: set[UUID] = field(default_factory=set)
    last_call: dict | None = None
    raises: Exception | None = None

    def availability_check(
        self,
        property_ids: list[UUID],
        check_in: date,
        check_out: date,
    ) -> AvailabilityResult:
        self.last_call = {
            "property_ids": list(property_ids),
            "check_in": check_in,
            "check_out": check_out,
        }
        if self.raises is not None:
            raise self.raises
        available = [pid for pid in property_ids if pid not in self.blocked_ids]
        blocked = [pid for pid in property_ids if pid in self.blocked_ids]
        return AvailabilityResult(available=available, blocked=blocked)


# ── Sample data ────────────────────────────────────────────────────────────────


def make_property(
    *,
    id: UUID | None = None,
    name: str = "Casa",
    location: str = "Bogota, Colombia",
    price_per_night: Decimal = Decimal("100"),
    currency: str = "COP",
    rating: float = 4.5,
    max_guests: int = 4,
    amenities: Iterable[str] = ("wifi",),
    status: int = 1,
    images: Iterable[PropertyImage] | None = None,
) -> PropertyMetadata:
    return PropertyMetadata(
        id=id or uuid4(),
        name=name,
        location=location,
        price_per_night=price_per_night,
        currency=currency,
        rating=rating,
        max_guests=max_guests,
        amenities=list(amenities),
        status=status,
        images=list(images or [PropertyImage(url="https://x/cover.jpg", is_cover=True)]),
    )


@pytest.fixture
def fake_properties() -> FakePropertiesServiceClient:
    return FakePropertiesServiceClient()


@pytest.fixture
def fake_reservations() -> FakeReservationsServiceClient:
    return FakeReservationsServiceClient()


@pytest.fixture
def client(fake_properties, fake_reservations):
    """TestClient with the HTTP dependencies overridden by in-memory fakes."""
    from assembly import (
        get_cache,
        get_properties_client,
        get_reservations_client,
    )
    from entrypoints.api.main import app

    app.dependency_overrides[get_properties_client] = lambda: fake_properties
    app.dependency_overrides[get_reservations_client] = lambda: fake_reservations
    app.dependency_overrides[get_cache] = lambda: None
    test_client = TestClient(app)
    yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def fake_redis():
    """In-memory Redis using fakeredis. No server required."""
    import fakeredis

    return fakeredis.FakeRedis(decode_responses=True)


@pytest.fixture
def cache(fake_redis):
    from adapters.cache.redis_cache import RedisCache
    from core.config import settings

    return RedisCache(client=fake_redis, ttl=settings.redis_cache_ttl_seconds)
