import json
import logging
from datetime import datetime, timezone
from uuid import UUID

import boto3
import httpx

from core.config import settings
from domain.ports.notification_dispatcher import NotificationDispatcher

logger = logging.getLogger(__name__)


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
                "payment_confirmed_at": datetime.now(timezone.utc).isoformat(),
            },
            headers={
                "X-Internal-Api-Key": settings.internal_api_key,
            },
            timeout=5.0,
        )
        response.raise_for_status()


class SqsNotificationDispatcher(NotificationDispatcher):
    """Publica el evento de confirmación de pago en la Notificaciones Queue (SQS).

    Alinea el flujo con el diagrama VC-004 (Gestor Reservas / Pagos -> SQS -> Gestor Notificaciones -> SES).
    El mensaje es JSON con el mismo schema que recibe /internal/payment-confirmations para reusar el use case.
    """

    def __init__(self, client=None, queue_url: str | None = None) -> None:
        self._client = client or boto3.client("sqs", region_name=settings.aws_region)
        self._queue_url = queue_url or settings.notifications_queue_url

    def dispatch_payment_confirmation(
        self,
        *,
        payment_id: UUID,
        source_ip: str | None = None,
    ) -> None:
        if not self._queue_url:
            raise RuntimeError(
                "NOTIFICATIONS_QUEUE_URL no esta configurado; no se puede publicar en SQS."
            )

        body = {
            "event_type": "payment_confirmation",
            "payment_id": str(payment_id),
            "source_ip": source_ip,
            "payment_confirmed_at": datetime.now(timezone.utc).isoformat(),
        }
        self._client.send_message(
            QueueUrl=self._queue_url,
            MessageBody=json.dumps(body),
            MessageAttributes={
                "event_type": {
                    "DataType": "String",
                    "StringValue": "payment_confirmation",
                },
            },
        )
        logger.info(
            "payment_confirmation_published",
            extra={"payment_id": str(payment_id), "queue_url": self._queue_url},
        )
