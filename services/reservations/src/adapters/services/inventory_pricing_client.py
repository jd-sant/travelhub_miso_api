from datetime import datetime
from decimal import Decimal
from uuid import UUID

import httpx

from core.config import settings
from domain.ports.pricing_service_client import PricingServiceClient


class HttpInventoryPricingClient(PricingServiceClient):
    def get_effective_price(
        self,
        property_id: UUID,
        check_in: datetime,
        check_out: datetime,
        guests: int,
    ) -> tuple[Decimal, str] | None:
        url = f"{settings.inventory_service_url}/api/v1/inventory/properties/{property_id}/availability"
        params = {
            "check_in": check_in.date().isoformat(),
            "check_out": check_out.date().isoformat(),
            "guests": max(1, guests),
        }
        try:
            response = httpx.get(url, params=params, timeout=5.0)
            response.raise_for_status()
        except httpx.HTTPError:
            return None

        payload = response.json()
        if not payload.get("available") or payload.get("price_from") is None:
            return None

        return Decimal(str(payload["price_from"])), str(payload.get("currency") or "COP")
