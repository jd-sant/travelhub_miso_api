"""Tests for the cache layer in the search use case + RedisCache adapter."""
from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock

from redis.exceptions import RedisError

from adapters.cache.redis_cache import RedisCache
from domain.schemas.search import SearchQuery
from domain.use_cases.search_properties import SearchPropertiesUseCase
from conftest import make_property


def _query(**overrides) -> SearchQuery:
    defaults = dict(
        city="Bogota",
        check_in=date(2026, 4, 10),
        check_out=date(2026, 4, 12),
        guests=2,
    )
    return SearchQuery(**(defaults | overrides))


# ── _cache_key ─────────────────────────────────────────────────────────────────


class TestCacheKey:
    def test_same_params_same_key(self):
        assert SearchPropertiesUseCase._cache_key(_query()) == SearchPropertiesUseCase._cache_key(_query())

    def test_amenities_order_independent(self):
        q1 = _query(amenities=["wifi", "pool"])
        q2 = _query(amenities=["pool", "wifi"])
        assert SearchPropertiesUseCase._cache_key(q1) == SearchPropertiesUseCase._cache_key(q2)

    def test_different_city_different_key(self):
        assert SearchPropertiesUseCase._cache_key(_query(city="Bogota")) != SearchPropertiesUseCase._cache_key(
            _query(city="Cali")
        )

    def test_different_dates_different_key(self):
        q1 = _query(check_in=date(2026, 4, 10), check_out=date(2026, 4, 12))
        q2 = _query(check_in=date(2026, 5, 10), check_out=date(2026, 5, 12))
        assert SearchPropertiesUseCase._cache_key(q1) != SearchPropertiesUseCase._cache_key(q2)

    def test_different_page_different_key(self):
        assert SearchPropertiesUseCase._cache_key(_query(page=1)) != SearchPropertiesUseCase._cache_key(
            _query(page=2)
        )

    def test_key_starts_with_search_prefix(self):
        assert SearchPropertiesUseCase._cache_key(_query()).startswith("search:")


# ── RedisCache adapter ─────────────────────────────────────────────────────────


class TestRedisCacheAdapter:
    def test_get_miss_returns_none(self, fake_redis):
        cache = RedisCache(fake_redis, ttl=300)
        assert cache.get("nope") is None

    def test_set_and_get_returns_same_data(self, fake_redis):
        cache = RedisCache(fake_redis, ttl=300)
        data = {"items": [], "total": 0, "page": 1, "page_size": 10}
        cache.set("k", data, ttl=300)
        assert cache.get("k") == data

    def test_ttl_is_applied(self, fake_redis):
        cache = RedisCache(fake_redis, ttl=300)
        cache.set("k", {"x": 1}, ttl=300)
        assert 0 < fake_redis.ttl("k") <= 300

    def test_get_redis_error_returns_none(self):
        bad = MagicMock()
        bad.get.side_effect = RedisError("boom")
        cache = RedisCache(bad, ttl=300)
        assert cache.get("k") is None

    def test_set_redis_error_does_not_raise(self):
        bad = MagicMock()
        bad.setex.side_effect = RedisError("boom")
        cache = RedisCache(bad, ttl=300)
        cache.set("k", {"x": 1}, ttl=300)  # must not raise


# ── Use case cache integration ─────────────────────────────────────────────────


class TestUseCaseCache:
    def test_second_call_is_cache_hit(self, fake_properties, fake_reservations, cache, fake_redis):
        p = make_property(name="Pp", location="Bogota, Colombia")
        fake_properties.catalog = [p]
        use_case = SearchPropertiesUseCase(fake_properties, fake_reservations, cache)

        first = use_case.execute(_query())
        # After first call the cache should be populated
        key = SearchPropertiesUseCase._cache_key(_query())
        assert fake_redis.exists(key) == 1

        # Second call: trigger; properties shouldn't matter — invalidate to confirm hit
        fake_properties.catalog = []
        second = use_case.execute(_query())
        assert second.total == first.total
        assert [it.id for it in second.items] == [it.id for it in first.items]

    def test_no_cache_works_identically(self, fake_properties, fake_reservations):
        p = make_property(location="Bogota, Colombia")
        fake_properties.catalog = [p]
        use_case = SearchPropertiesUseCase(fake_properties, fake_reservations, cache=None)

        result = use_case.execute(_query())
        assert result.total == 1

    def test_malformed_cache_falls_through_and_deletes(
        self, fake_properties, fake_reservations, fake_redis, cache
    ):
        # Pre-populate cache with malformed payload
        key = SearchPropertiesUseCase._cache_key(_query())
        fake_redis.set(key, '{"total": 1}')  # missing required fields

        p = make_property(location="Bogota, Colombia")
        fake_properties.catalog = [p]
        use_case = SearchPropertiesUseCase(fake_properties, fake_reservations, cache)

        result = use_case.execute(_query())
        # Malformed entry was discarded and a fresh result was computed and re-cached
        assert result.total == 1
        # The freshly cached value should be valid now
        cached_after = cache.get(key)
        assert cached_after is not None
        assert cached_after["total"] == 1
