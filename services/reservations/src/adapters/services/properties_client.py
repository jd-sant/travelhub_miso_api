from uuid import UUID

import httpx

from core.config import settings
from errors import ServiceUnavailableError


class PropertiesServiceClient:
    """HTTP client for the properties service."""

    def __init__(self, base_url: str | None = None, timeout: float = 5.0):
        self.base_url = (base_url or settings.properties_service_url).rstrip("/")
        self.timeout = timeout

    def list_by_owner(self, owner_id: UUID) -> list[dict]:
        url = f"{self.base_url}/api/v1/properties"
        try:
            response = httpx.get(
                url,
                params={"owner_id": str(owner_id)},
                timeout=self.timeout,
            )
        except httpx.RequestError as exc:
            raise ServiceUnavailableError(
                "No se pudo conectar al servicio de propiedades"
            ) from exc

        if response.status_code != 200:
            raise ServiceUnavailableError(
                f"Properties service responded with {response.status_code}"
            )
        return response.json()

    def get_owned_property_ids(self, owner_id: UUID) -> list[UUID]:
        return [UUID(item["id"]) for item in self.list_by_owner(owner_id)]
