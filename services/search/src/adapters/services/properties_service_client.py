"""HTTP client to the properties microservice."""
from uuid import UUID

import httpx

from core.config import settings
from domain.ports.properties_service import PropertiesServicePort, PropertyQuery
from domain.schemas.external import PropertiesPage, PropertyMetadata
from errors import PropertiesServiceUnavailableError


class HttpPropertiesServiceClient(PropertiesServicePort):
    def __init__(self, base_url: str | None = None, timeout: float | None = None):
        self._base_url = (base_url or settings.properties_service_url).rstrip("/")
        self._timeout = timeout if timeout is not None else settings.service_request_timeout

    def search(self, query: PropertyQuery) -> PropertiesPage:
        params: list[tuple[str, str]] = []
        if query.city:
            params.append(("city", query.city))
        if query.min_price is not None:
            params.append(("min_price", str(query.min_price)))
        if query.max_price is not None:
            params.append(("max_price", str(query.max_price)))
        if query.min_guests is not None:
            params.append(("min_guests", str(query.min_guests)))
        if query.check_in:
            params.append(("check_in", query.check_in))
        if query.check_out:
            params.append(("check_out", query.check_out))
        for amenity in query.amenities:
            params.append(("amenities", amenity))
        for pid in query.ids:
            params.append(("ids", str(pid)))
        if query.min_lat is not None:
            params.append(("min_lat", str(query.min_lat)))
        if query.max_lat is not None:
            params.append(("max_lat", str(query.max_lat)))
        if query.min_lng is not None:
            params.append(("min_lng", str(query.min_lng)))
        if query.max_lng is not None:
            params.append(("max_lng", str(query.max_lng)))
        params.append(("page", str(query.page)))
        params.append(("page_size", str(query.page_size)))
        params.append(("sort_by", query.sort_by))
        params.append(("sort_dir", query.sort_dir))

        url = f"{self._base_url}/api/v1/properties/search"
        try:
            response = httpx.get(url, params=params, timeout=self._timeout)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise PropertiesServiceUnavailableError(
                "Could not reach the properties service"
            ) from exc

        payload = response.json()
        return PropertiesPage(
            items=[PropertyMetadata(**item) for item in payload.get("items", [])],
            total=payload["pagination"]["total"],
            page=payload["pagination"]["page"],
            page_size=payload["pagination"]["page_size"],
            total_pages=payload["pagination"]["total_pages"],
        )

    def get_by_id(self, property_id: UUID) -> PropertyMetadata | None:
        url = f"{self._base_url}/api/v1/properties/{property_id}"
        try:
            response = httpx.get(url, timeout=self._timeout)
            if response.status_code == 404:
                return None
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise PropertiesServiceUnavailableError(
                "Could not reach the properties service"
            ) from exc

        return PropertyMetadata(**response.json())
