from uuid import UUID

import httpx

from core.config import settings
from errors import ServiceUnavailableError


class UsersServiceClient:
    """HTTP client for the internal users service endpoints."""

    def __init__(self, base_url: str | None = None, timeout: float = 5.0):
        self.base_url = (base_url or settings.users_service_url).rstrip("/")
        self.timeout = timeout

    def _headers(self) -> dict:
        return {"X-Internal-Api-Key": settings.internal_api_key}

    def search_by_name(self, query: str) -> list[dict]:
        if not query or not query.strip():
            return []
        url = f"{self.base_url}/api/v1/internal/users/search-by-name"
        try:
            response = httpx.post(
                url,
                json={"query": query.strip()},
                headers=self._headers(),
                timeout=self.timeout,
            )
        except httpx.RequestError as exc:
            raise ServiceUnavailableError(
                "No se pudo conectar al servicio de usuarios"
            ) from exc
        if response.status_code != 200:
            raise ServiceUnavailableError(
                f"Users service responded with {response.status_code}"
            )
        return response.json()

    def list_by_ids(self, ids: list[UUID]) -> list[dict]:
        if not ids:
            return []
        url = f"{self.base_url}/api/v1/internal/users/by-ids"
        try:
            response = httpx.post(
                url,
                json={"ids": [str(i) for i in ids]},
                headers=self._headers(),
                timeout=self.timeout,
            )
        except httpx.RequestError as exc:
            raise ServiceUnavailableError(
                "No se pudo conectar al servicio de usuarios"
            ) from exc
        if response.status_code != 200:
            raise ServiceUnavailableError(
                f"Users service responded with {response.status_code}"
            )
        return response.json()
