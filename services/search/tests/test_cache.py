"""Tests for cache layer: correctness, hit/miss, silent failure, key generation."""
from datetime import date
from unittest.mock import MagicMock

import pytest
from redis.exceptions import RedisError

from adapters.cache.redis_cache import RedisCache
from adapters.repositories.search_repository import _make_cache_key
from domain.schemas.search import SearchQuery


# ── Helpers ────────────────────────────────────────────────────────────────────

def make_query(**overrides) -> SearchQuery:
    defaults = dict(
        city="Bogota",
        check_in=date(2026, 4, 10),
        check_out=date(2026, 4, 12),
        guests=2,
    )
    return SearchQuery(**(defaults | overrides))


# ── _make_cache_key ────────────────────────────────────────────────────────────

class TestMakeCacheKey:

    def test_same_params_produce_same_key(self):
        assert _make_cache_key(make_query()) == _make_cache_key(make_query())

    def test_amenities_order_independent(self):
        q1 = make_query(amenities=["wifi", "pool"])
        q2 = make_query(amenities=["pool", "wifi"])
        assert _make_cache_key(q1) == _make_cache_key(q2)

    def test_different_city_different_key(self):
        assert _make_cache_key(make_query(city="Bogota")) != _make_cache_key(make_query(city="Cali"))

    def test_different_dates_different_key(self):
        q1 = make_query(check_in=date(2026, 4, 10), check_out=date(2026, 4, 12))
        q2 = make_query(check_in=date(2026, 5, 10), check_out=date(2026, 5, 12))
        assert _make_cache_key(q1) != _make_cache_key(q2)

    def test_different_page_different_key(self):
        assert _make_cache_key(make_query(page=1)) != _make_cache_key(make_query(page=2))

    def test_key_starts_with_search_prefix(self):
        assert _make_cache_key(make_query()).startswith("search:")


# ── RedisCache ─────────────────────────────────────────────────────────────────

class TestRedisCache:

    def test_get_miss_returns_none(self, fake_redis):
        cache = RedisCache(fake_redis, ttl=300)
        assert cache.get("nonexistent") is None

    def test_set_and_get_returns_same_data(self, fake_redis):
        cache = RedisCache(fake_redis, ttl=300)
        data = {"items": [], "total": 0, "page": 1, "page_size": 10}

        cache.set("mykey", data, ttl=300)

        assert cache.get("mykey") == data

    def test_ttl_is_applied(self, fake_redis):
        cache = RedisCache(fake_redis, ttl=300)
        cache.set("mykey", {"x": 1}, ttl=300)

        ttl = fake_redis.ttl("mykey")
        assert 0 < ttl <= 300

    def test_get_redis_error_returns_none(self):
        """Silent failure: Redis errors must not propagate."""
        bad_client = MagicMock()
        bad_client.get.side_effect = RedisError("connection reset")
        cache = RedisCache(bad_client, ttl=300)

        assert cache.get("any_key") is None

    def test_set_redis_error_does_not_raise(self):
        """Silent failure: SET errors must not propagate."""
        bad_client = MagicMock()
        bad_client.setex.side_effect = RedisError("connection reset")
        cache = RedisCache(bad_client, ttl=300)

        cache.set("any_key", {"data": 1}, ttl=300)  # must not raise


# ── Repository cache correctness ───────────────────────────────────────────────

class TestSearchRepositoryCacheCorrectness:

    def test_result_with_cache_equals_result_without_cache(
        self, search_repository, search_repository_with_cache
    ):
        """CA: cached result is identical to DB result."""
        query = make_query()

        result_db = search_repository.search(query)
        result_cache = search_repository_with_cache.search(query)  # miss + stores

        assert result_db.total == result_cache.total
        assert result_db.items == result_cache.items

    def test_second_call_is_cache_hit(self, search_repository_with_cache, fake_redis):
        """CA: second identical search returns from Redis (key exists)."""
        query = make_query()

        search_repository_with_cache.search(query)   # cache miss
        key = _make_cache_key(query)
        assert fake_redis.exists(key) == 1           # data stored

        result_2 = search_repository_with_cache.search(query)  # cache hit

        assert result_2 is not None

    def test_cache_none_works_identically_to_no_cache(self, search_repository):
        """With cache=None the repository functions exactly as before."""
        query = make_query()
        result = search_repository.search(query)
        assert result is not None


class TestSearchRepositoryMalformedCache:

    def test_malformed_cache_is_treated_as_miss_and_deleted(
        self, search_repository, fake_redis
    ):
        query = make_query()
        key = _make_cache_key(query)
        fake_redis.set(key, '{"total": 1, "page": 1, "page_size": 10}')

        cache = RedisCache(fake_redis, ttl=300)
        delete_spy = MagicMock(wraps=cache.delete)
        cache.delete = delete_spy
        repo = type(search_repository)(search_repository.session, cache)

        result = repo.search(query)

        assert result is not None
        delete_spy.assert_called_once_with(key)
