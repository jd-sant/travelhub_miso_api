"""Consumer SQS que procesa eventos para el servicio de pagos.

Alinea el flujo con el diagrama VC-004: el mensaje publicado por el servicio
`reservations` (event_type=refund_request) en la Payments Queue es consumido
aqui, y se ejecuta `CreateReservationRefundUseCase` que crea el reembolso en
Stripe y registra el resultado en la DB.

Es fire-and-forget: reservations no espera respuesta. Si el refund falla, el
mensaje queda visible y se reintenta (eventualmente DLQ).
"""

from __future__ import annotations

import json
import logging
import signal
import time
from typing import Any

import boto3
from sqlmodel import Session

from adapters.gateways.stripe_checkout_gateway import StripeSdkCheckoutGateway
from adapters.repositories.payment_audit_repository import SQLModelPaymentAuditRepository
from adapters.repositories.payment_repository import SQLModelPaymentRepository
from core.config import settings
from db.session import engine
from domain.schemas.payment import ReservationRefundRequest
from domain.use_cases.create_reservation_refund import CreateReservationRefundUseCase

logger = logging.getLogger(__name__)


class SqsPaymentsConsumer:
    def __init__(
        self,
        client: Any | None = None,
        queue_url: str | None = None,
    ) -> None:
        self._client = client or boto3.client("sqs", region_name=settings.aws_region)
        self._queue_url = queue_url or settings.payments_queue_url
        if not self._queue_url:
            raise RuntimeError("PAYMENTS_QUEUE_URL no esta configurado.")
        self._running = False

    def stop(self, *_args: Any) -> None:
        logger.info("sqs_payments_consumer_stopping")
        self._running = False

    def run_forever(self) -> None:
        self._running = True
        signal.signal(signal.SIGTERM, self.stop)
        signal.signal(signal.SIGINT, self.stop)
        logger.info("sqs_payments_consumer_started", extra={"queue_url": self._queue_url})

        while self._running:
            try:
                self._poll_once()
            except Exception:  # noqa: BLE001
                logger.exception("sqs_payments_consumer_poll_error")
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
                    "sqs_payments_message_handling_failed",
                    extra={"message_id": message.get("MessageId")},
                )

    def _handle_message(self, message: dict[str, Any]) -> None:
        body_raw = message.get("Body", "{}")
        try:
            body = json.loads(body_raw)
        except json.JSONDecodeError:
            logger.error("sqs_payments_message_invalid_json", extra={"body": body_raw[:500]})
            raise

        event_type = body.get("event_type", "refund_request")
        if event_type == "refund_request":
            self._handle_refund_request(body)
        else:
            logger.warning("sqs_payments_unknown_event_type", extra={"event_type": event_type})

    def _handle_refund_request(self, body: dict[str, Any]) -> None:
        request = ReservationRefundRequest(**body)
        with Session(engine) as session:
            use_case = CreateReservationRefundUseCase(
                repository=SQLModelPaymentRepository(session),
                audit_repository=SQLModelPaymentAuditRepository(session),
                gateway=StripeSdkCheckoutGateway(),
            )
            use_case.execute(request)
