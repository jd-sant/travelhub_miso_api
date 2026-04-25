import json
import logging
from datetime import datetime, timezone
from uuid import UUID

import boto3

from core.config import settings
from domain.ports.hotel_side_effects import (
    ReservationNotificationDispatcher,
    ReservationRefundDispatcher,
)

logger = logging.getLogger(__name__)


class NoOpReservationNotificationDispatcher(ReservationNotificationDispatcher):
    def dispatch_reservation_update(
        self,
        *,
        traveler_id: UUID,
        reservation_id: UUID,
        status: str,
        reason: str,
        source_ip: str | None = None,
        refund_requested: bool = False,
    ) -> None:
        return None


class SqsReservationNotificationDispatcher(ReservationNotificationDispatcher):
    """Publica el evento de actualizacion de reserva en la Notifications Queue (SQS).

    Alinea el flujo con el diagrama VC-004: reservations -> SQS -> notifications-worker -> SES.
    El consumer en notifications filtra por event_type=reservation_update y reusa
    `CreateReservationUpdateUseCase` y `SendPaymentConfirmationUseCase`.
    """

    def __init__(self, client=None, queue_url: str | None = None) -> None:
        self._client = client or boto3.client("sqs", region_name=settings.aws_region)
        self._queue_url = queue_url or settings.notifications_queue_url

    def dispatch_reservation_update(
        self,
        *,
        traveler_id: UUID,
        reservation_id: UUID,
        status: str,
        reason: str,
        source_ip: str | None = None,
        refund_requested: bool = False,
    ) -> None:
        if not self._queue_url:
            raise RuntimeError(
                "NOTIFICATIONS_QUEUE_URL no esta configurado; no se puede publicar en SQS."
            )

        body = {
            "event_type": "reservation_update",
            "traveler_id": str(traveler_id),
            "reservation_id": str(reservation_id),
            "status": status,
            "reason": reason,
            "source_ip": source_ip,
            "refund_requested": refund_requested,
            "occurred_at": datetime.now(timezone.utc).isoformat(),
        }
        self._client.send_message(
            QueueUrl=self._queue_url,
            MessageBody=json.dumps(body),
            MessageAttributes={
                "event_type": {
                    "DataType": "String",
                    "StringValue": "reservation_update",
                },
            },
        )
        logger.info(
            "reservation_update_published",
            extra={
                "reservation_id": str(reservation_id),
                "status": status,
                "queue_url": self._queue_url,
            },
        )


class NoOpReservationRefundDispatcher(ReservationRefundDispatcher):
    def request_refund(
        self,
        *,
        reservation_id: UUID,
        cancellation_reason: str,
        source_ip: str | None = None,
    ) -> None:
        return None


class SqsReservationRefundDispatcher(ReservationRefundDispatcher):
    """Publica un evento `refund_request` en la Payments Queue (SQS).

    El payments-worker consume el evento y ejecuta `CreateReservationRefundUseCase`.
    Es fire-and-forget: no se espera el monto reembolsado de vuelta.
    """

    def __init__(self, client=None, queue_url: str | None = None) -> None:
        self._client = client or boto3.client("sqs", region_name=settings.aws_region)
        self._queue_url = queue_url or settings.payments_queue_url

    def request_refund(
        self,
        *,
        reservation_id: UUID,
        cancellation_reason: str,
        source_ip: str | None = None,
    ) -> None:
        if not self._queue_url:
            raise RuntimeError(
                "PAYMENTS_QUEUE_URL no esta configurado; no se puede publicar en SQS."
            )

        body = {
            "event_type": "refund_request",
            "reservation_id": str(reservation_id),
            "reason": cancellation_reason[:255],
            "source_ip": source_ip,
            "requested_at": datetime.now(timezone.utc).isoformat(),
        }
        self._client.send_message(
            QueueUrl=self._queue_url,
            MessageBody=json.dumps(body),
            MessageAttributes={
                "event_type": {
                    "DataType": "String",
                    "StringValue": "refund_request",
                },
            },
        )
        logger.info(
            "refund_request_published",
            extra={
                "reservation_id": str(reservation_id),
                "queue_url": self._queue_url,
            },
        )
