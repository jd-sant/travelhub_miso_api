from uuid import UUID

import httpx

from core.config import settings
from errors import PricingServiceUnavailableError


class PropertiesOwnershipClient:
    def __init__(self, base_url: str | None = None, timeout: float | None = None):
        self.base_url = (base_url or settings.properties_service_url).rstrip("/")
        self.timeout = settings.service_request_timeout if timeout is None else timeout

    def list_owned_property_ids(self, owner_id: UUID) -> set[UUID]:
        url = f"{self.base_url}/api/v1/properties"
        try:
            response = httpx.get(
                url,
                params={"owner_id": str(owner_id)},
                timeout=self.timeout,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise PricingServiceUnavailableError(
                "No se pudo validar la propiedad del hotel porque el servicio de propiedades no está disponible"
            ) from exc
        return {UUID(item["id"]) for item in response.json()}
