from abc import ABC, abstractmethod
from typing import Optional


class CachePort(ABC):
    """Cache port for the search domain. Implementation-agnostic."""

    @abstractmethod
    def get(self, key: str) -> Optional[dict]:
        """
        Returns the value for the key, or None if not found / expired.
        The value is always a JSON-serializable dict.
        """

    @abstractmethod
    def set(self, key: str, value: dict, ttl: int) -> None:
        """
        Stores value under key with a TTL in seconds.
        Silent failure: must not raise exceptions if the cache backend fails.
        """

    @abstractmethod
    def delete(self, key: str) -> None:
        """
        Removes the key from cache.
        Silent failure: must not raise exceptions if the cache backend fails.
        """

    @abstractmethod
    def get_ttl(self) -> int:
        """
        Returns the default TTL (time-to-live) in seconds for cache entries.
        """
