"""HTTP client to the reservations microservice (internal availability endpoint)."""
from datetime import date
from uuid import UUID

import httpx

from core.config import settings
from domain.ports.reservations_service import ReservationsServicePort
from domain.schemas.external import AvailabilityResult
from errors import ReservationsServiceUnavailableError


class HttpReservationsServiceClient(ReservationsServicePort):
    def __init__(
        self,
        base_url: str | None = None,
        timeout: float | None = None,
        api_key: str | None = None,
    ):
        self._base_url = (base_url or settings.reservations_service_url).rstrip("/")
        self._timeout = timeout if timeout is not None else settings.service_request_timeout
        self._api_key = api_key if api_key is not None else settings.internal_api_key

    def availability_check(
        self,
        property_ids: list[UUID],
        check_in: date,
        check_out: date,
    ) -> AvailabilityResult:
        if not property_ids:
            return AvailabilityResult(available=[], blocked=[])

        url = f"{self._base_url}/api/v1/internal/reservations/availability-check"
        body = {
            "property_ids": [str(pid) for pid in property_ids],
            "check_in": check_in.isoformat(),
            "check_out": check_out.isoformat(),
        }
        try:
            response = httpx.post(
                url,
                json=body,
                headers={"X-Internal-Api-Key": self._api_key},
                timeout=self._timeout,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ReservationsServiceUnavailableError(
                "Could not reach the reservations service"
            ) from exc

        payload = response.json()
        return AvailabilityResult(
            available=[UUID(x) for x in payload.get("available", [])],
            blocked=[UUID(x) for x in payload.get("blocked", [])],
        )
