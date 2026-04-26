from decimal import Decimal
from uuid import UUID

import httpx

from core.config import settings
from domain.ports.property_service_client import PropertyServiceClient
from domain.schemas.property_service import (
    PropertyCancellationPolicyResponse,
    PropertyDetailResponse,
)
from errors import PropertyNotFoundError, PropertyServiceUnavailableError


class HttpPropertyServiceClient(PropertyServiceClient):
    def get_property(self, property_id: UUID) -> PropertyDetailResponse:
        url = f"{settings.properties_service_url}/api/v1/properties/{property_id}"
        try:
            response = httpx.get(url, timeout=5.0)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                raise PropertyNotFoundError(f"Property {property_id} not found") from exc
            raise PropertyServiceUnavailableError(
                "No se pudo consultar el servicio de propiedades"
            ) from exc
        except httpx.HTTPError as exc:
            raise PropertyServiceUnavailableError(
                "No se pudo consultar el servicio de propiedades"
            ) from exc

        payload = response.json()
        images = payload.get("images") or []
        cover = next(
            (img.get("url") for img in images if img.get("is_cover")),
            (images[0].get("url") if images else None),
        )
        return PropertyDetailResponse(
            id=payload["id"],
            max_guests=payload["max_guests"],
            price_per_night=Decimal(str(payload.get("price_per_night", 0))),
            name=payload.get("name"),
            cover_image_url=cover,
            cleaning_fee=Decimal(str(payload.get("cleaning_fee", 0))),
            tax_rate=Decimal(str(payload.get("tax_rate", 0))),
        )

    def get_cancellation_policy(
        self, property_id: UUID
    ) -> PropertyCancellationPolicyResponse:
        url = (
            f"{settings.properties_service_url}"
            f"/api/v1/internal/properties/{property_id}/cancellation-policy"
        )
        try:
            response = httpx.get(
                url,
                headers={"X-Internal-Api-Key": settings.internal_api_key},
                timeout=5.0,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                raise PropertyNotFoundError(
                    f"Cancellation policy for property {property_id} not found"
                ) from exc
            raise PropertyServiceUnavailableError(
                "No se pudo consultar la politica de cancelacion"
            ) from exc
        except httpx.HTTPError as exc:
            raise PropertyServiceUnavailableError(
                "No se pudo consultar la politica de cancelacion"
            ) from exc

        payload = response.json()
        return PropertyCancellationPolicyResponse(**payload)
