import db.redis as redis_db


class _FakeRedis:
    def __init__(self, connection_pool):
        self.connection_pool = connection_pool


def test_get_redis_client_retries_after_interval(monkeypatch):
    monkeypatch.setenv("REDIS_CACHE_ENABLED", "true")
    monkeypatch.setattr(redis_db, "_pool", None)
    monkeypatch.setattr(redis_db, "_next_retry_at", 0.0)
    monkeypatch.setattr(redis_db, "_retry_interval_seconds", 5.0)
    monkeypatch.setattr(redis_db, "Redis", _FakeRedis)

    attempts = {"count": 0}
    first_pool = object()

    def fake_build_pool():
        attempts["count"] += 1
        if attempts["count"] == 1:
            return None
        return first_pool

    ticks = iter([10.0, 12.0, 16.0])
    monkeypatch.setattr(redis_db.time, "monotonic", lambda: next(ticks))
    monkeypatch.setattr(redis_db, "_build_pool", fake_build_pool)

    assert redis_db.get_redis_client() is None
    assert redis_db.get_redis_client() is None
    client = redis_db.get_redis_client()

    assert attempts["count"] == 2
    assert client is not None
    assert client.connection_pool is first_pool


def test_get_redis_client_disables_and_clears_pool(monkeypatch):
    class _FakePool:
        def __init__(self):
            self.disconnected = False

        def disconnect(self):
            self.disconnected = True

    pool = _FakePool()
    monkeypatch.setenv("REDIS_CACHE_ENABLED", "false")
    monkeypatch.setattr(redis_db, "_pool", pool)
    monkeypatch.setattr(redis_db, "_next_retry_at", 99.0)

    client = redis_db.get_redis_client()

    assert client is None
    assert pool.disconnected is True
    assert redis_db._pool is None
    assert redis_db._next_retry_at == 0.0