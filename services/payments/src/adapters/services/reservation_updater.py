from uuid import UUID

import httpx

from core.config import settings
from domain.ports.notification_dispatcher import ReservationUpdater


class NoOpReservationUpdater(ReservationUpdater):
    def confirm_reservation(
        self,
        *,
        reservation_id: UUID,
        source_ip: str | None = None,
    ) -> None:
        return None


class HttpReservationUpdater(ReservationUpdater):
    def confirm_reservation(
        self,
        *,
        reservation_id: UUID,
        source_ip: str | None = None,
    ) -> None:
        if not settings.reservations_service_url:
            return None

        url = (
            f"{settings.reservations_service_url}"
            f"/api/v1/internal/reservations/{reservation_id}/status"
        )
        response = httpx.patch(
            url,
            json={"status": "confirmed"},
            headers={
                "X-Internal-Api-Key": settings.internal_api_key,
            },
            timeout=5.0,
        )
        response.raise_for_status()
