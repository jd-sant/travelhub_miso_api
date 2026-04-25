"""Tests de los dispatchers SQS introducidos para MPF-36 (reservation-updates por SQS)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from adapters.services.hotel_side_effects import (
    SqsReservationNotificationDispatcher,
    SqsReservationRefundDispatcher,
)


def test_sqs_notification_dispatcher_publishes_reservation_update_event():
    sqs_client = MagicMock()
    dispatcher = SqsReservationNotificationDispatcher(
        client=sqs_client,
        queue_url="https://sqs.us-east-1.amazonaws.com/000000000000/notifications-queue",
    )

    traveler_id = uuid4()
    reservation_id = uuid4()
    dispatcher.dispatch_reservation_update(
        traveler_id=traveler_id,
        reservation_id=reservation_id,
        status="cancelled",
        reason="maintenance",
        source_ip="10.0.0.1",
        refund_requested=True,
    )

    sqs_client.send_message.assert_called_once()
    kwargs = sqs_client.send_message.call_args.kwargs
    assert kwargs["QueueUrl"].endswith("notifications-queue")
    body = json.loads(kwargs["MessageBody"])
    assert body["event_type"] == "reservation_update"
    assert body["traveler_id"] == str(traveler_id)
    assert body["reservation_id"] == str(reservation_id)
    assert body["status"] == "cancelled"
    assert body["reason"] == "maintenance"
    assert body["source_ip"] == "10.0.0.1"
    assert body["refund_requested"] is True
    assert "refund_amount_in_cents" not in body
    assert kwargs["MessageAttributes"]["event_type"]["StringValue"] == "reservation_update"


def test_sqs_notification_dispatcher_fails_without_queue_url():
    dispatcher = SqsReservationNotificationDispatcher(client=MagicMock(), queue_url="")
    with pytest.raises(RuntimeError, match="NOTIFICATIONS_QUEUE_URL"):
        dispatcher.dispatch_reservation_update(
            traveler_id=uuid4(),
            reservation_id=uuid4(),
            status="confirmed",
            reason="manual",
        )


def test_sqs_refund_dispatcher_publishes_refund_request_event():
    sqs_client = MagicMock()
    dispatcher = SqsReservationRefundDispatcher(
        client=sqs_client,
        queue_url="https://sqs.us-east-1.amazonaws.com/000000000000/payments-queue",
    )

    reservation_id = uuid4()
    dispatcher.request_refund(
        reservation_id=reservation_id,
        cancellation_reason="hotel_cancelled_by_host",
        source_ip="10.0.0.2",
    )

    sqs_client.send_message.assert_called_once()
    kwargs = sqs_client.send_message.call_args.kwargs
    assert kwargs["QueueUrl"].endswith("payments-queue")
    body = json.loads(kwargs["MessageBody"])
    assert body["event_type"] == "refund_request"
    assert body["reservation_id"] == str(reservation_id)
    assert body["reason"] == "hotel_cancelled_by_host"
    assert body["source_ip"] == "10.0.0.2"
    assert kwargs["MessageAttributes"]["event_type"]["StringValue"] == "refund_request"


def test_sqs_refund_dispatcher_truncates_long_reason():
    sqs_client = MagicMock()
    dispatcher = SqsReservationRefundDispatcher(
        client=sqs_client,
        queue_url="https://sqs.us-east-1.amazonaws.com/000000000000/payments-queue",
    )

    long_reason = "x" * 500
    dispatcher.request_refund(
        reservation_id=uuid4(),
        cancellation_reason=long_reason,
    )

    body = json.loads(sqs_client.send_message.call_args.kwargs["MessageBody"])
    assert len(body["reason"]) == 255


def test_sqs_refund_dispatcher_fails_without_queue_url():
    dispatcher = SqsReservationRefundDispatcher(client=MagicMock(), queue_url="")
    with pytest.raises(RuntimeError, match="PAYMENTS_QUEUE_URL"):
        dispatcher.request_refund(
            reservation_id=uuid4(),
            cancellation_reason="reason",
        )


def test_sqs_refund_dispatcher_returns_none():
    """El dispatcher es fire-and-forget: no devuelve nada al caller."""
    sqs_client = MagicMock()
    dispatcher = SqsReservationRefundDispatcher(
        client=sqs_client,
        queue_url="https://sqs.us-east-1.amazonaws.com/000000000000/payments-queue",
    )

    result = dispatcher.request_refund(
        reservation_id=uuid4(),
        cancellation_reason="reason",
    )

    assert result is None
