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

    def notify_refund_result(
        self,
        *,
        reservation_id: UUID,
        status: str,
        amount_in_cents: int,
        refund_id: UUID,
        source_ip: str | None = None,
    ) -> None:
        return None

    def notify_additional_charge_result(
        self,
        *,
        reservation_id: UUID,
        status: str,
        amount_in_cents: int,
        payment_id: UUID,
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

    def notify_refund_result(
        self,
        *,
        reservation_id: UUID,
        status: str,
        amount_in_cents: int,
        refund_id: UUID,
        source_ip: str | None = None,
    ) -> None:
        if not settings.reservations_service_url:
            return None

        url = (
            f"{settings.reservations_service_url}"
            f"/api/v1/internal/reservations/{reservation_id}/refund-result"
        )
        response = httpx.post(
            url,
            json={
                "status": status,
                "refund_id": str(refund_id),
                "amount_in_cents": amount_in_cents,
            },
            headers={
                "X-Internal-Api-Key": settings.internal_api_key,
            },
            timeout=5.0,
        )
        response.raise_for_status()

    def notify_additional_charge_result(
        self,
        *,
        reservation_id: UUID,
        status: str,
        amount_in_cents: int,
        payment_id: UUID,
        source_ip: str | None = None,
    ) -> None:
        if not settings.reservations_service_url:
            return None

        url = (
            f"{settings.reservations_service_url}"
            f"/api/v1/internal/reservations/{reservation_id}/additional-charge-result"
        )
        response = httpx.post(
            url,
            json={
                "status": status,
                "payment_id": str(payment_id),
                "amount_in_cents": amount_in_cents,
            },
            headers={
                "X-Internal-Api-Key": settings.internal_api_key,
            },
            timeout=5.0,
        )
        response.raise_for_status()
