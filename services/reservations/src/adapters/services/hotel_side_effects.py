from uuid import UUID

import httpx

from core.config import settings
from domain.ports.hotel_side_effects import (
    ReservationNotificationDispatcher,
    ReservationRefundDispatcher,
)


class NoOpReservationNotificationDispatcher(ReservationNotificationDispatcher):
    def dispatch_reservation_update(
        self,
        *,
        traveler_id: UUID,
        reservation_id: UUID,
        status: str,
        reason: str,
        locale: str | None = None,
        reason_code: str | None = None,
        reason_note: str | None = None,
        source_ip: str | None = None,
        refund_requested: bool = False,
        refund_amount_in_cents: int | None = None,
    ) -> None:
        return None


class HttpReservationNotificationDispatcher(ReservationNotificationDispatcher):
    def __init__(self):
        self._client = httpx.Client(timeout=5.0)

    def dispatch_reservation_update(
        self,
        *,
        traveler_id: UUID,
        reservation_id: UUID,
        status: str,
        reason: str,
        locale: str | None = None,
        reason_code: str | None = None,
        reason_note: str | None = None,
        source_ip: str | None = None,
        refund_requested: bool = False,
        refund_amount_in_cents: int | None = None,
    ) -> None:
        if not settings.notifications_service_url:
            return None
        response = self._client.post(
            f"{settings.notifications_service_url}/api/v1/internal/reservation-updates",
            json={
                "traveler_id": str(traveler_id),
                "reservation_id": str(reservation_id),
                "status": status,
                "reason": reason,
                "locale": locale,
                "reason_code": reason_code,
                "reason_note": reason_note,
                "source_ip": source_ip,
                "refund_requested": refund_requested,
                "refund_amount_in_cents": refund_amount_in_cents,
            },
            headers={"X-Internal-Api-Key": settings.internal_api_key},
        )
        response.raise_for_status()


class NoOpReservationRefundDispatcher(ReservationRefundDispatcher):
    def request_refund(
        self,
        *,
        reservation_id: UUID,
        cancellation_reason: str,
        source_ip: str | None = None,
    ) -> dict | None:
        return None


class HttpReservationRefundDispatcher(ReservationRefundDispatcher):
    def __init__(self):
        self._client = httpx.Client(timeout=10.0)

    def request_refund(
        self,
        *,
        reservation_id: UUID,
        cancellation_reason: str,
        source_ip: str | None = None,
    ) -> dict | None:
        if not settings.payments_service_url:
            return None
        response = self._client.post(
            f"{settings.payments_service_url}/api/v1/internal/refunds",
            json={
                "reservation_id": str(reservation_id),
                "reason": cancellation_reason[:255],
                "source_ip": source_ip,
            },
            headers={"X-Internal-Api-Key": settings.internal_api_key},
        )
        response.raise_for_status()
        return response.json()
