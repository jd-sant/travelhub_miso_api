from uuid import UUID

import httpx

from core.config import settings
from domain.ports.notification_dispatcher import NotificationDispatcher


class NoOpNotificationDispatcher(NotificationDispatcher):
    def dispatch_payment_confirmation(
        self,
        *,
        payment_id: UUID,
        source_ip: str | None = None,
    ) -> None:
        return None


class HttpNotificationDispatcher(NotificationDispatcher):
    def dispatch_payment_confirmation(
        self,
        *,
        payment_id: UUID,
        source_ip: str | None = None,
    ) -> None:
        if not settings.notifications_service_url:
            return None

        url = f"{settings.notifications_service_url}/api/v1/internal/payment-confirmations"
        response = httpx.post(
            url,
            json={
                "payment_id": str(payment_id),
                "source_ip": source_ip,
            },
            headers={
                "X-Internal-Api-Key": settings.internal_api_key,
            },
            timeout=5.0,
        )
        response.raise_for_status()
