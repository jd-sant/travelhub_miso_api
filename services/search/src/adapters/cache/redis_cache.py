import json
import logging
from typing import Optional

from redis import Redis
from redis.exceptions import RedisError

from domain.ports.cache_port import CachePort

logger = logging.getLogger(__name__)


class RedisCache(CachePort):
    """
    CachePort implementation using Redis.
    Silent failure: if Redis fails, get() returns None and set() is a no-op.
    """

    def __init__(self, client: Redis, ttl: int) -> None:
        self._client = client
        self._ttl = ttl

    def get(self, key: str) -> Optional[dict]:
        try:
            raw = self._client.get(key)
            if raw is None:
                logger.debug("cache miss: %s", key)
                return None
            logger.debug("cache hit: %s", key)
            return json.loads(raw)
        except (RedisError, json.JSONDecodeError) as exc:
            logger.warning("Redis GET failed for %s: %s", key, exc)
            return None

    def set(self, key: str, value: dict, ttl: int) -> None:
        try:
            self._client.setex(key, ttl, json.dumps(value, default=str))
            logger.debug("cache set: %s (ttl=%ds)", key, ttl)
        except (RedisError, TypeError) as exc:
            logger.warning("Redis SET failed for %s: %s", key, exc)

    def delete(self, key: str) -> None:
        try:
            self._client.delete(key)
            logger.debug("cache delete: %s", key)
        except RedisError as exc:
            logger.warning("Redis DELETE failed for %s: %s", key, exc)

    def get_ttl(self) -> int:
        return self._ttl
