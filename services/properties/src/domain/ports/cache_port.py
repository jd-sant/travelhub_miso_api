from abc import ABC, abstractmethod
from typing import Optional


class CachePort(ABC):
    """Generic cache port for JSON-serializable payloads."""

    @abstractmethod
    def get(self, key: str) -> Optional[dict | list]:
        """Return cached payload or None on miss/error."""

    @abstractmethod
    def set(self, key: str, value: dict | list, ttl: int) -> None:
        """Store payload with TTL. Silent failure on backend issues."""

    @abstractmethod
    def delete(self, key: str) -> None:
        """Delete cached key. Silent failure on backend issues."""

    @abstractmethod
    def get_ttl(self) -> int:
        """Default TTL in seconds for cache entries."""
