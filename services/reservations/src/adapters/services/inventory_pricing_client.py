from datetime import datetime
from decimal import Decimal
import logging
from uuid import UUID

import httpx

from core.config import settings
from domain.ports.pricing_service_client import PricingServiceClient

logger = logging.getLogger(__name__)


class NoOpInventoryPricingClient(PricingServiceClient):
    def get_effective_price(
        self,
        property_id: UUID,
        check_in: datetime,
        check_out: datetime,
        guests: int,
    ) -> tuple[Decimal, str] | None:
        return None


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
            response = httpx.get(url, params=params, timeout=settings.service_request_timeout)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning("inventory pricing lookup failed for property %s: %s", property_id, exc)
            return None

        payload = response.json()
        if not payload.get("available") or payload.get("price_from") is None:
            return None
        currency = payload.get("currency")
        if not currency:
            logger.warning(
                "inventory pricing response missing currency for property %s between %s and %s",
                property_id,
                params["check_in"],
                params["check_out"],
            )
            return None

        return Decimal(str(payload["price_from"])), str(currency)
