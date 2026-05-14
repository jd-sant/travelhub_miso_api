from datetime import date
from uuid import UUID

import httpx

from core.config import settings
from domain.ports.inventory_service import InventoryServicePort
from domain.schemas.availability import PropertyAvailabilityResponse
from errors import InventoryServiceUnavailableError


class HttpInventoryServiceClient(InventoryServicePort):
    def __init__(self, base_url: str | None = None, timeout: float | None = None):
        self._base_url = (base_url or settings.inventory_service_url).rstrip("/")
        self._timeout = timeout if timeout is not None else settings.service_request_timeout

    def get_availability(
        self,
        property_id: UUID,
        check_in: date,
        check_out: date,
        guests: int,
    ) -> PropertyAvailabilityResponse:
        url = f"{self._base_url}/api/v1/inventory/properties/{property_id}/availability"
        try:
            response = httpx.get(
                url,
                params={
                    "check_in": check_in.isoformat(),
                    "check_out": check_out.isoformat(),
                    "guests": max(1, guests),
                },
                timeout=self._timeout,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise InventoryServiceUnavailableError(
                "Could not reach the inventory service"
            ) from exc
        return PropertyAvailabilityResponse(**response.json())
