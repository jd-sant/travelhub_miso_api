from datetime import datetime
from uuid import UUID

import httpx

from core.config import settings
from errors import ServiceUnavailableError


class PaymentsServiceClient:
    """HTTP client for the payments service internal endpoints."""

    def __init__(self, base_url: str | None = None, timeout: float = 5.0):
        self.base_url = (base_url or settings.payments_service_url).rstrip("/")
        self.timeout = timeout

    def aggregate(
        self,
        reservation_ids: list[UUID],
        *,
        status: str = "confirmed",
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        granularity: str | None = None,
    ) -> dict:
        if not reservation_ids:
            return {
                "total_amount_cents": 0,
                "currency": None,
                "count": 0,
                "buckets": [],
            }
        url = f"{self.base_url}/api/v1/internal/payments/aggregate"
        body = {
            "reservation_ids": [str(rid) for rid in reservation_ids],
            "status": status,
        }
        if start_date is not None:
            body["start_date"] = start_date.isoformat()
        if end_date is not None:
            body["end_date"] = end_date.isoformat()
        if granularity is not None:
            body["granularity"] = granularity

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
