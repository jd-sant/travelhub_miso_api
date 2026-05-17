"""Tests del SqsNotificationDispatcher usado en HU022 / MPF-29."""

from __future__ import annotations

import json
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from adapters.services.notification_dispatcher import SqsNotificationDispatcher


def test_sqs_dispatcher_publica_mensaje_con_payment_confirmed_at():
    sqs_client = MagicMock()
    dispatcher = SqsNotificationDispatcher(
        client=sqs_client,
        queue_url="https://sqs.us-east-1.amazonaws.com/000000000000/test-queue",
    )

    payment_id = uuid4()
    dispatcher.dispatch_payment_confirmation(payment_id=payment_id, source_ip="10.0.0.1")

    sqs_client.send_message.assert_called_once()
    kwargs = sqs_client.send_message.call_args.kwargs
    assert kwargs["QueueUrl"].endswith("test-queue")
    body = json.loads(kwargs["MessageBody"])
    assert body["event_type"] == "payment_confirmation"
    assert body["payment_id"] == str(payment_id)
    assert body["source_ip"] == "10.0.0.1"
    assert "payment_confirmed_at" in body and body["payment_confirmed_at"]
    assert kwargs["MessageAttributes"]["event_type"]["StringValue"] == "payment_confirmation"


def test_sqs_dispatcher_falla_sin_queue_url():
    dispatcher = SqsNotificationDispatcher(client=MagicMock(), queue_url="")
    with pytest.raises(RuntimeError, match="NOTIFICATIONS_QUEUE_URL"):
        dispatcher.dispatch_payment_confirmation(payment_id=uuid4())
