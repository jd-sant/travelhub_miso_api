from uuid import UUID

import httpx

from core.config import settings
from errors import ServiceUnavailableError


class PaymentsServiceClient:
    """HTTP client for the payments service internal endpoints."""

    def __init__(self, base_url: str | None = None, timeout: float = 5.0):
        self.base_url = (base_url or settings.payments_service_url).rstrip("/")
        self.timeout = timeout

    def list_by_reservations(
        self,
        reservation_ids: list[UUID],
        *,
        status: str = "confirmed",
    ) -> dict:
        if not reservation_ids:
            return {"items": [], "available_currencies": []}
        url = f"{self.base_url}/api/v1/internal/payments/by-reservations"
        body = {
            "reservation_ids": [str(rid) for rid in reservation_ids],
            "status": status,
        }
        try:
            response = httpx.post(
                url,
                json=body,
                headers={"X-Internal-Api-Key": settings.internal_api_key},
                timeout=self.timeout,
            )
        except httpx.RequestError as exc:
            raise ServiceUnavailableError(
                "No se pudo conectar al servicio de pagos"
            ) from exc

        if response.status_code != 200:
            raise ServiceUnavailableError(
                f"Payments service responded with {response.status_code}"
            )
        return response.json()
