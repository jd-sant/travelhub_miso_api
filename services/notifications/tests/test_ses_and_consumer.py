"""Tests para SES sender, consumer SQS y observabilidad SLA (HU022 / MPF-29)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from adapters.services.ses_email_sender import SesEmailSender


def test_ses_sender_envia_html():
    client = MagicMock()
    client.send_raw_email.return_value = {"MessageId": "ses-msg-1"}
    sender = SesEmailSender(client=client, from_address="no-reply@travelhub.test")

    message_id = sender.send(
        recipient_email="user@example.com",
        subject="Confirmacion",
        html_body="<p>Hola html</p>",
    )

    assert message_id == "ses-msg-1"
    client.send_raw_email.assert_called_once()
    call_kwargs = client.send_raw_email.call_args.kwargs
    assert call_kwargs["Source"] == "no-reply@travelhub.test"
    assert call_kwargs["Destinations"] == ["user@example.com"]
    raw_bytes = call_kwargs["RawMessage"]["Data"]
    assert b"Hola html" in raw_bytes
    assert b"text/html" in raw_bytes


def test_ses_sender_falla_sin_from_address():
    sender = SesEmailSender(client=MagicMock(), from_address="")
    with pytest.raises(RuntimeError, match="SES_FROM_ADDRESS"):
        sender.send(recipient_email="u@e.com", subject="s", html_body="<p>b</p>")


def test_send_payment_confirmation_registra_latencia():
    """El use case debe calcular latency_ms y marcar sla_30s_met correctamente."""
    from domain.schemas.notification import (
        NotificationRecord,
        NotificationStatus,
    )
    from domain.use_cases.send_payment_confirmation import SendPaymentConfirmationUseCase

    notification_repo = MagicMock()
    delivery_repo = MagicMock()
    audit_repo = MagicMock()
    email_sender = MagicMock()
    email_sender.send.return_value = "msg-1"

    notification_id = uuid4()
    notification = NotificationRecord(
        notification_id=notification_id,
        traveler_id=uuid4(),
        reservation_id=uuid4(),
        payment_id=uuid4(),
        channel="email",
        template_code="payment_confirmation_v1",
        status=NotificationStatus.pending,
        subject="Confirmacion",
        recipient_email="user@example.com",
        recipient_name="Viajero",
        payload={
            "payment_summary": {
                "reservation_id": "RES-1",
                "receipt_number": "TH-1",
                "property_name": "Casa Prueba",
                "property_address": "Calle 1",
                "check_in_date": "2026-05-10",
                "check_out_date": "2026-05-12",
                "guests_count": 2,
                "nights": 2,
                "nightly_rate_in_cents": 10000,
                "taxes_in_cents": 1600,
                "total_in_cents": 21600,
                "amount_in_cents": 21600,
                "currency": "USD",
                "cancellation_policy": "Test policy",
            }
        },
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    notification_repo.get_by_id.return_value = notification
    notification_repo.update.side_effect = lambda n: n

    use_case = SendPaymentConfirmationUseCase(
        notification_repository=notification_repo,
        delivery_attempt_repository=delivery_repo,
        audit_repository=audit_repo,
        email_sender=email_sender,
    )

    payment_confirmed_at = datetime.now(timezone.utc) - timedelta(seconds=2)
    use_case.execute(notification_id, payment_confirmed_at=payment_confirmed_at)

    # Audit log recibido con los 3 timestamps + latency_ms
    audit_repo.add_log.assert_called_once()
    audit_payload = audit_repo.add_log.call_args.args[0].payload
    assert "payment_confirmed_at" in audit_payload
    assert "notification_created_at" in audit_payload
    assert "email_sent_at" in audit_payload
    assert audit_payload["latency_ms"] < 30_000

    # Email se envía con html_body conteniendo los campos enriquecidos
    send_kwargs = email_sender.send.call_args.kwargs
    assert "Calle 1" in send_kwargs["html_body"]
    assert "Test policy" in send_kwargs["html_body"]


def test_sqs_consumer_procesa_mensaje_y_lo_elimina(monkeypatch):
    """El consumer parsea el mensaje, dispara use cases y elimina el receipt handle."""
    import adapters.services.sqs_notification_consumer as module
    from adapters.services.sqs_notification_consumer import SqsNotificationConsumer

    sqs_client = MagicMock()
    sqs_client.receive_message.return_value = {
        "Messages": [
            {
                "MessageId": "m1",
                "ReceiptHandle": "handle-1",
                "Body": json.dumps(
                    {
                        "event_type": "payment_confirmation",
                        "payment_id": str(uuid4()),
                        "source_ip": "10.0.0.1",
                        "payment_confirmed_at": datetime.now(timezone.utc).isoformat(),
                    }
                ),
            }
        ]
    }

    # Stub de use cases: evitamos DB real
    created_notification = MagicMock(
        notification_id=uuid4(),
        status=MagicMock(),
    )
    created_notification.status.__eq__ = lambda self, other: False  # not sent

    class StubCreateUseCase:
        def __init__(self, *args, **kwargs): ...
        def execute(self, request):
            return created_notification

    class StubSendUseCase:
        executed = False

        def __init__(self, *args, **kwargs): ...
        def execute(self, notification_id, **kwargs):
            StubSendUseCase.executed = True

    monkeypatch.setattr(module, "CreatePaymentConfirmationUseCase", StubCreateUseCase)
    monkeypatch.setattr(module, "SendPaymentConfirmationUseCase", StubSendUseCase)
    monkeypatch.setattr(module, "Session", lambda engine: MagicMock(__enter__=lambda s: s, __exit__=lambda *a: None))
    monkeypatch.setattr(module, "HttpPaymentConfirmationClient", lambda: MagicMock())
    monkeypatch.setattr(module, "HttpTravelerProfileClient", lambda: MagicMock())
    monkeypatch.setattr(module, "SQLModelNotificationRepository", lambda s: MagicMock())
    monkeypatch.setattr(module, "SQLModelDeliveryAttemptRepository", lambda s: MagicMock())
    monkeypatch.setattr(module, "SQLModelNotificationAuditRepository", lambda s: MagicMock())

    consumer = SqsNotificationConsumer(
        email_sender=MagicMock(),
        client=sqs_client,
        queue_url="https://sqs/test-queue",
    )
    consumer._poll_once()

    assert StubSendUseCase.executed is True
    sqs_client.delete_message.assert_called_once_with(
        QueueUrl="https://sqs/test-queue",
        ReceiptHandle="handle-1",
    )
