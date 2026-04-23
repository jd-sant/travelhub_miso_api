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
        cover_image_url: str | None = None
        images = payload.get("images", [])
        for img in images:
            if img.get("is_cover"):
                cover_image_url = img.get("url")
                break
        if cover_image_url is None and images:
            cover_image_url = images[0].get("url")
        return PropertyDetailResponse(
            id=payload["id"],
            max_guests=payload["max_guests"],
            name=payload.get("name", ""),
            cover_image_url=cover_image_url,
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
