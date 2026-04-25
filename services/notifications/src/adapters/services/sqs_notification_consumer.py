"""Consumer SQS que procesa eventos de notificación.

Alinea el flujo con el diagrama VC-004: los mensajes publicados por los servicios
`payments` (event_type=payment_confirmation) y `reservations` (event_type=reservation_update)
en la Notifications Queue son consumidos aquí; se crea la notificación y se
despacha el email (SES/SMTP según configuración del assembly).
"""

from __future__ import annotations

import json
import logging
import signal
import time
from typing import Any

import boto3
from sqlmodel import Session

from adapters.repositories.delivery_attempt_repository import SQLModelDeliveryAttemptRepository
from adapters.repositories.notification_audit_repository import SQLModelNotificationAuditRepository
from adapters.repositories.notification_repository import SQLModelNotificationRepository
from adapters.services.payment_confirmation_client import HttpPaymentConfirmationClient
from adapters.services.traveler_profile_client import HttpTravelerProfileClient
from core.config import settings
from db.session import engine
from domain.ports.email_sender import EmailSender
from domain.schemas.notification import (
    NotificationStatus,
    PaymentConfirmationRequest,
    ReservationUpdateRequest,
)
from domain.use_cases.create_payment_confirmation import CreatePaymentConfirmationUseCase
from domain.use_cases.create_reservation_update import CreateReservationUpdateUseCase
from domain.use_cases.send_payment_confirmation import SendPaymentConfirmationUseCase

logger = logging.getLogger(__name__)


class SqsNotificationConsumer:
    def __init__(
        self,
        email_sender: EmailSender,
        client: Any | None = None,
        queue_url: str | None = None,
    ) -> None:
        self._email_sender = email_sender
        self._client = client or boto3.client("sqs", region_name=settings.aws_region)
        self._queue_url = queue_url or settings.notifications_queue_url
        if not self._queue_url:
            raise RuntimeError("NOTIFICATIONS_QUEUE_URL no esta configurado.")
        self._running = False

    def stop(self, *_args: Any) -> None:
        logger.info("sqs_consumer_stopping")
        self._running = False

    def run_forever(self) -> None:
        self._running = True
        signal.signal(signal.SIGTERM, self.stop)
        signal.signal(signal.SIGINT, self.stop)
        logger.info("sqs_consumer_started", extra={"queue_url": self._queue_url})

        while self._running:
            try:
                self._poll_once()
            except Exception:  # noqa: BLE001
                logger.exception("sqs_consumer_poll_error")
                time.sleep(2)

    def _poll_once(self) -> None:
        response = self._client.receive_message(
            QueueUrl=self._queue_url,
            MaxNumberOfMessages=settings.sqs_max_messages,
            WaitTimeSeconds=settings.sqs_poll_wait_seconds,
            MessageAttributeNames=["All"],
        )
        messages = response.get("Messages", [])
        for message in messages:
            receipt_handle = message.get("ReceiptHandle")
            try:
                self._handle_message(message)
                self._client.delete_message(
                    QueueUrl=self._queue_url,
                    ReceiptHandle=receipt_handle,
                )
            except Exception:  # noqa: BLE001
                logger.exception(
                    "sqs_message_handling_failed",
                    extra={"message_id": message.get("MessageId")},
                )

    def _handle_message(self, message: dict[str, Any]) -> None:
        body_raw = message.get("Body", "{}")
        try:
            body = json.loads(body_raw)
        except json.JSONDecodeError:
            logger.error("sqs_message_invalid_json", extra={"body": body_raw[:500]})
            # Mensaje malformado: borramos via la excepción (lo dejamos reintentar y caer a DLQ).
            raise

        event_type = body.get("event_type", "payment_confirmation")
        if event_type == "payment_confirmation":
            self._handle_payment_confirmation(body)
        elif event_type == "reservation_update":
            self._handle_reservation_update(body)
        else:
            logger.warning("sqs_unknown_event_type", extra={"event_type": event_type})

    def _handle_payment_confirmation(self, body: dict[str, Any]) -> None:
        request = PaymentConfirmationRequest(**body)
        with Session(engine) as session:
            create_use_case = CreatePaymentConfirmationUseCase(
                notification_repository=SQLModelNotificationRepository(session),
                audit_repository=SQLModelNotificationAuditRepository(session),
                payment_confirmation_source=HttpPaymentConfirmationClient(),
                traveler_profile_source=HttpTravelerProfileClient(),
            )
            notification = create_use_case.execute(request)

            if notification.status == NotificationStatus.sent:
                return

            send_use_case = SendPaymentConfirmationUseCase(
                notification_repository=SQLModelNotificationRepository(session),
                delivery_attempt_repository=SQLModelDeliveryAttemptRepository(session),
                audit_repository=SQLModelNotificationAuditRepository(session),
                email_sender=self._email_sender,
            )
            send_use_case.execute(
                notification.notification_id,
                source_ip=request.source_ip,
                payment_confirmed_at=request.payment_confirmed_at,
            )

    def _handle_reservation_update(self, body: dict[str, Any]) -> None:
        request = ReservationUpdateRequest(**body)
        with Session(engine) as session:
            create_use_case = CreateReservationUpdateUseCase(
                notification_repository=SQLModelNotificationRepository(session),
                audit_repository=SQLModelNotificationAuditRepository(session),
                traveler_profile_source=HttpTravelerProfileClient(),
            )
            notification = create_use_case.execute(request)

            if notification.status == NotificationStatus.sent:
                return

            send_use_case = SendPaymentConfirmationUseCase(
                notification_repository=SQLModelNotificationRepository(session),
                delivery_attempt_repository=SQLModelDeliveryAttemptRepository(session),
                audit_repository=SQLModelNotificationAuditRepository(session),
                email_sender=self._email_sender,
            )
            send_use_case.execute(
                notification.notification_id,
                source_ip=request.source_ip,
            )
