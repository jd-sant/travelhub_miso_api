from datetime import datetime, timezone
from uuid import uuid4

from adapters.repositories.cached_property_repository import CachedPropertyRepository
from domain.ports.property_repository import PropertyRepository
from domain.schemas.property import PropertyListResponse, PropertyResponse
from domain.schemas.property_policy import (
    CancellationPolicyType,
    PropertyCancellationPolicyResponse,
)


class FakeCache:
    def __init__(self):
        self.store: dict[str, dict | list] = {}
        self.ttl = 300

    def get(self, key: str):
        return self.store.get(key)

    def set(self, key: str, value: dict | list, ttl: int) -> None:
        self.store[key] = value
        self.ttl = ttl

    def delete(self, key: str) -> None:
        self.store.pop(key, None)

    def get_ttl(self) -> int:
        return self.ttl


class FakePropertyRepository(PropertyRepository):
    def __init__(self, detail: PropertyResponse, listing: list[PropertyListResponse], policy: PropertyCancellationPolicyResponse):
        self.detail = detail
        self.listing = listing
        self.policy = policy
        self.detail_calls = 0
        self.list_calls = 0
        self.policy_calls = 0

    def get_by_id(self, property_id):
        self.detail_calls += 1
        return self.detail if self.detail.id == property_id else None

    def list_all(self, owner_id=None):
        self.list_calls += 1
        if owner_id is None:
            return self.listing
        return [item for item in self.listing if item.id_owner == owner_id]

    def get_cancellation_policy(self, property_id):
        self.policy_calls += 1
        return self.policy if self.policy.property_id == property_id else None


def _sample_detail() -> PropertyResponse:
    property_id = uuid4()
    owner_id = uuid4()
    return PropertyResponse(
        id=property_id,
        id_owner=owner_id,
        name="Cached Suites",
        description="Fast property detail",
        location="Bogotá, Colombia",
        latitude=4.711,
        longitude=-74.0721,
        price_per_night=420.0,
        currency="USD",
        rating=4.8,
        review_count=22,
        bedrooms=2,
        bathrooms=2.0,
        max_guests=4,
        amenities=["WiFi", "Breakfast"],
        cancellation_policy="Flexible",
        tax_rate=0.19,
        cleaning_fee=35.0,
        images=[],
        reviews=[],
        status=1,
    )


def _sample_list(detail: PropertyResponse) -> list[PropertyListResponse]:
    return [
        PropertyListResponse(
            id=detail.id,
            id_owner=detail.id_owner,
            name=detail.name,
            description=detail.description,
            location=detail.location,
            latitude=detail.latitude,
            longitude=detail.longitude,
            price_per_night=detail.price_per_night,
            currency=detail.currency,
            rating=detail.rating,
            review_count=detail.review_count,
            bedrooms=detail.bedrooms,
            bathrooms=detail.bathrooms,
            max_guests=detail.max_guests,
            amenities=detail.amenities,
            cancellation_policy=detail.cancellation_policy,
            tax_rate=detail.tax_rate,
            cleaning_fee=detail.cleaning_fee,
            images=detail.images,
            status=detail.status,
        )
    ]


def _sample_policy(detail: PropertyResponse) -> PropertyCancellationPolicyResponse:
    now = datetime.now(timezone.utc)
    return PropertyCancellationPolicyResponse(
        property_id=detail.id,
        policy_type=CancellationPolicyType.full_refund,
        minimum_notice_hours=24,
        penalty_percentage=0,
        timezone="America/Bogota",
        is_active=True,
        created_at=now,
        updated_at=now,
    )


def test_property_detail_uses_cache_after_first_load():
    detail = _sample_detail()
    repository = FakePropertyRepository(detail, _sample_list(detail), _sample_policy(detail))
    cache = FakeCache()
    cached_repository = CachedPropertyRepository(repository, cache)

    first = cached_repository.get_by_id(detail.id)
    second = cached_repository.get_by_id(detail.id)

    assert first == detail
    assert second == detail
    assert repository.detail_calls == 1
    assert cache.get(f"properties:detail:{detail.id}") is not None


def test_property_list_uses_cache_after_first_load():
    detail = _sample_detail()
    listing = _sample_list(detail)
    repository = FakePropertyRepository(detail, listing, _sample_policy(detail))
    cache = FakeCache()
    cached_repository = CachedPropertyRepository(repository, cache)

    first = cached_repository.list_all()
    second = cached_repository.list_all()

    assert first == listing
    assert second == listing
    assert repository.list_calls == 1
    assert cache.get("properties:list:all") is not None


def test_property_policy_uses_cache_after_first_load():
    detail = _sample_detail()
    policy = _sample_policy(detail)
    repository = FakePropertyRepository(detail, _sample_list(detail), policy)
    cache = FakeCache()
    cached_repository = CachedPropertyRepository(repository, cache)

    first = cached_repository.get_cancellation_policy(detail.id)
    second = cached_repository.get_cancellation_policy(detail.id)

    assert first == policy
    assert second == policy
    assert repository.policy_calls == 1
    assert cache.get(f"properties:policy:{detail.id}") is not None


def test_invalid_cached_detail_is_treated_as_miss():
    detail = _sample_detail()
    repository = FakePropertyRepository(detail, _sample_list(detail), _sample_policy(detail))
    cache = FakeCache()
    cache.set(f"properties:detail:{detail.id}", {"bad": "payload"}, ttl=300)
    cached_repository = CachedPropertyRepository(repository, cache)

    result = cached_repository.get_by_id(detail.id)

    assert result == detail
    assert repository.detail_calls == 1
