"""Tests del SqsPaymentsConsumer (refund_request via SQS)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

import adapters.services.sqs_payments_consumer as module
from adapters.services.sqs_payments_consumer import SqsPaymentsConsumer


def test_consumer_falla_sin_queue_url():
    with pytest.raises(RuntimeError, match="PAYMENTS_QUEUE_URL"):
        SqsPaymentsConsumer(client=MagicMock(), queue_url="")


def test_consumer_procesa_refund_request_y_borra_mensaje(monkeypatch):
    sqs_client = MagicMock()
    reservation_id = uuid4()
    sqs_client.receive_message.return_value = {
        "Messages": [
            {
                "MessageId": "m1",
                "ReceiptHandle": "handle-1",
                "Body": json.dumps(
                    {
                        "event_type": "refund_request",
                        "reservation_id": str(reservation_id),
                        "reason": "hotel_cancelled_by_host",
                        "source_ip": "10.0.0.1",
                    }
                ),
            }
        ]
    }

    class StubCreateRefund:
        called_with = None

        def __init__(self, *args, **kwargs): ...

        def execute(self, request):
            StubCreateRefund.called_with = request
            return MagicMock()

    monkeypatch.setattr(module, "CreateReservationRefundUseCase", StubCreateRefund)
    monkeypatch.setattr(
        module,
        "Session",
        lambda engine: MagicMock(__enter__=lambda s: s, __exit__=lambda *a: None),
    )
    monkeypatch.setattr(module, "SQLModelPaymentRepository", lambda s: MagicMock())
    monkeypatch.setattr(module, "SQLModelPaymentAuditRepository", lambda s: MagicMock())
    monkeypatch.setattr(module, "StripeSdkCheckoutGateway", lambda: MagicMock())

    consumer = SqsPaymentsConsumer(
        client=sqs_client,
        queue_url="https://sqs.us-east-1.amazonaws.com/000000000000/payments-queue",
    )
    consumer._poll_once()

    assert StubCreateRefund.called_with is not None
    assert StubCreateRefund.called_with.reservation_id == reservation_id
    assert StubCreateRefund.called_with.reason == "hotel_cancelled_by_host"
    assert StubCreateRefund.called_with.source_ip == "10.0.0.1"
    sqs_client.delete_message.assert_called_once_with(
        QueueUrl="https://sqs.us-east-1.amazonaws.com/000000000000/payments-queue",
        ReceiptHandle="handle-1",
    )


def test_consumer_ignora_event_type_desconocido(monkeypatch):
    sqs_client = MagicMock()
    sqs_client.receive_message.return_value = {
        "Messages": [
            {
                "MessageId": "m1",
                "ReceiptHandle": "handle-1",
                "Body": json.dumps(
                    {
                        "event_type": "something_else",
                        "reservation_id": str(uuid4()),
                    }
                ),
            }
        ]
    }

    class StubCreateRefund:
        invoked = False

        def __init__(self, *args, **kwargs): ...

        def execute(self, request):
            StubCreateRefund.invoked = True

    monkeypatch.setattr(module, "CreateReservationRefundUseCase", StubCreateRefund)

    consumer = SqsPaymentsConsumer(
        client=sqs_client,
        queue_url="https://sqs/payments-queue",
    )
    consumer._poll_once()

    assert StubCreateRefund.invoked is False
    # Mensaje aun se borra para no acumular ruido en la cola
    sqs_client.delete_message.assert_called_once()


def test_consumer_no_borra_mensaje_si_use_case_falla(monkeypatch):
    sqs_client = MagicMock()
    sqs_client.receive_message.return_value = {
        "Messages": [
            {
                "MessageId": "m1",
                "ReceiptHandle": "handle-1",
                "Body": json.dumps(
                    {
                        "event_type": "refund_request",
                        "reservation_id": str(uuid4()),
                        "reason": "test",
                    }
                ),
            }
        ]
    }

    class FailingCreateRefund:
        def __init__(self, *args, **kwargs): ...

        def execute(self, request):
            raise RuntimeError("payment not found")

    monkeypatch.setattr(module, "CreateReservationRefundUseCase", FailingCreateRefund)
    monkeypatch.setattr(
        module,
        "Session",
        lambda engine: MagicMock(__enter__=lambda s: s, __exit__=lambda *a: None),
    )
    monkeypatch.setattr(module, "SQLModelPaymentRepository", lambda s: MagicMock())
    monkeypatch.setattr(module, "SQLModelPaymentAuditRepository", lambda s: MagicMock())
    monkeypatch.setattr(module, "StripeSdkCheckoutGateway", lambda: MagicMock())

    consumer = SqsPaymentsConsumer(
        client=sqs_client,
        queue_url="https://sqs/payments-queue",
    )
    consumer._poll_once()

    sqs_client.delete_message.assert_not_called()
