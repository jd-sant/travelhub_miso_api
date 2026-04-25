from types import SimpleNamespace
from uuid import uuid4

from sqlmodel import Session, select

from adapters.models.payment_audit_log import PaymentAuditLog
from adapters.models.payment_checkout_session import PaymentCheckoutSession
from adapters.models.payment import Payment
from adapters.models.payment_event import PaymentEvent
from adapters.models.payment_processing_outbox import PaymentProcessingOutbox
from adapters.models.payment_reservation_confirmation_outbox import (
    PaymentReservationConfirmationOutbox,
)
from adapters.services.in_process_payment_processing_runner import (
    InProcessPaymentProcessingRunner,
)
from assembly import (
    get_notification_dispatcher,
    get_payment_processing_runner,
    get_reservation_updater,
    get_stripe_checkout_gateway,
)
from core.config import settings
from core.security import build_request_checksum, hash_token
from entrypoints.api.routers import payments as payments_router

from .conftest import (
    FakeNotificationDispatcher,
    FakeReservationUpdater,
    FakeStripeCheckoutGateway,
    SECURE_HEADERS,
    build_charge_payload as _payload,
    build_checkout_payload as _checkout_payload,
)


def test_create_payment_success_generates_receipt_and_events(client, test_engine):
    payload = _payload()

    response = client.post("/api/v1/payments/charges", json=payload, headers=SECURE_HEADERS)

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "confirmed"
    assert body["provider_code"] == "fake_stripe"
    assert body["currency"] == "COP"
    assert body["receipt_id"] is not None
    assert body["receipt_number"].startswith("RCPT-")
    assert body["failure_reason"] is None
    assert "payment_method_token" not in body

    with Session(test_engine) as session:
        stored_payment = session.exec(select(Payment)).first()
        stored_events = session.exec(select(PaymentEvent)).all()
        stored_audit_logs = session.exec(select(PaymentAuditLog)).all()

    assert stored_payment is not None
    assert stored_payment.provider_code == "fake_stripe"
    assert stored_payment.payment_method_token_hash == hash_token(payload["payment_method_token"])
    assert stored_payment.payment_method_token_hash != payload["payment_method_token"]
    assert {event.event_type for event in stored_events} == {
        "payment.succeeded",
        "reservation.confirmation.requested",
        "inventory.update.requested",
        "receipt.generated",
    }
    assert {log.action for log in stored_audit_logs} == {
        "payment.charge.confirmed",
        "reservation.confirmation.requested",
        "notification.payment_confirmation.requested",
    }


def test_create_payment_failure_returns_clear_reason(client, test_engine):
    payload = _payload(token="pm_fail_insufficient_funds")

    response = client.post("/api/v1/payments/charges", json=payload, headers=SECURE_HEADERS)

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "failed"
    assert body["provider_code"] == "fake_stripe"
    assert body["failure_reason"] == "insufficient_funds"
    assert body["receipt_id"] is None

    with Session(test_engine) as session:
        stored_events = session.exec(select(PaymentEvent)).all()

    assert [event.event_type for event in stored_events] == ["payment.failed"]


def test_create_payment_success_dispatches_notification_request(client):
    dispatcher = FakeNotificationDispatcher()
    client.app.dependency_overrides[get_notification_dispatcher] = lambda: dispatcher

    response = client.post("/api/v1/payments/charges", json=_payload(), headers=SECURE_HEADERS)

    assert response.status_code == 201
    assert len(dispatcher.calls) == 1
    assert str(dispatcher.calls[0]["payment_id"]) == response.json()["payment_id"]


def test_create_payment_success_dispatches_reservation_confirmation(client):
    updater = FakeReservationUpdater()
    client.app.dependency_overrides[get_reservation_updater] = lambda: updater

    response = client.post("/api/v1/payments/charges", json=_payload(), headers=SECURE_HEADERS)

    assert response.status_code == 201
    assert len(updater.calls) == 1
    assert str(updater.calls[0]["reservation_id"]) == response.json()["reservation_id"]


def test_create_payment_success_does_not_fail_when_notification_dispatch_fails(client, test_engine):
    dispatcher = FakeNotificationDispatcher(should_fail=True)
    client.app.dependency_overrides[get_notification_dispatcher] = lambda: dispatcher

    response = client.post("/api/v1/payments/charges", json=_payload(), headers=SECURE_HEADERS)

    assert response.status_code == 201

    with Session(test_engine) as session:
        stored_audit_logs = session.exec(select(PaymentAuditLog)).all()

    assert "notification.payment_confirmation.dispatch_failed" in {
        log.action for log in stored_audit_logs
    }


def test_create_payment_success_does_not_fail_when_reservation_update_fails(client, test_engine):
    updater = FakeReservationUpdater(should_fail=True)
    client.app.dependency_overrides[get_reservation_updater] = lambda: updater

    response = client.post("/api/v1/payments/charges", json=_payload(), headers=SECURE_HEADERS)

    assert response.status_code == 201

    with Session(test_engine) as session:
        stored_audit_logs = session.exec(select(PaymentAuditLog)).all()
        outbox_items = session.exec(select(PaymentReservationConfirmationOutbox)).all()

    assert "reservation.confirmation.dispatch_failed" in {
        log.action for log in stored_audit_logs
    }
    assert len(outbox_items) == 1
    assert outbox_items[0].status == "pending"
    assert outbox_items[0].attempt_count == 1


def test_retry_reservation_confirmations_processes_pending_outbox(client, test_engine):
    failing_updater = FakeReservationUpdater(should_fail=True)
    client.app.dependency_overrides[get_reservation_updater] = lambda: failing_updater

    create_response = client.post("/api/v1/payments/charges", json=_payload(), headers=SECURE_HEADERS)

    assert create_response.status_code == 201

    with Session(test_engine) as session:
        outbox_item = session.exec(select(PaymentReservationConfirmationOutbox)).first()

    assert outbox_item is not None
    assert outbox_item.status == "pending"

    success_updater = FakeReservationUpdater(should_fail=False)
    client.app.dependency_overrides[get_reservation_updater] = lambda: success_updater

    retry_response = client.post(
        "/api/v1/internal/reservation-confirmations/retry",
        headers={"X-Internal-Api-Key": settings.internal_api_key},
    )

    assert retry_response.status_code == 200
    body = retry_response.json()
    assert body["processed_count"] == 1
    assert body["succeeded_count"] == 1
    assert body["failed_count"] == 0

    with Session(test_engine) as session:
        updated_outbox = session.exec(select(PaymentReservationConfirmationOutbox)).first()

    assert updated_outbox is not None
    assert updated_outbox.status == "succeeded"


def test_retry_reservation_confirmations_requires_internal_api_key(client):
    response = client.post(
        "/api/v1/internal/reservation-confirmations/retry",
        headers={"X-Internal-Api-Key": "invalid-key"},
    )

    assert response.status_code == 403


def test_create_payment_card_declined_returns_clear_reason(client):
    payload = _payload(token="pm_fail_card_declined")

    response = client.post("/api/v1/payments/charges", json=payload, headers=SECURE_HEADERS)

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "failed"
    assert body["failure_reason"] == "card_declined"


def test_create_payment_rejects_raw_card_fields(client):
    payload = _payload()
    payload["card_number"] = "4242424242424242"
    payload["cvv"] = "123"
    payload["expiration_date"] = "12/30"

    response = client.post("/api/v1/payments/charges", json=payload, headers=SECURE_HEADERS)

    assert response.status_code == 422
    detail = response.json()["detail"]
    rejected_fields = {error["loc"][-1] for error in detail}
    assert {"card_number", "cvv", "expiration_date"} <= rejected_fields


def test_create_payment_rejects_duplicate_within_two_seconds(client):
    payload = _payload()
    second_payload = payload.copy()
    second_payload["idempotency_key"] = "booking-123-attempt-2"

    first_response = client.post("/api/v1/payments/charges", json=payload, headers=SECURE_HEADERS)
    second_response = client.post("/api/v1/payments/charges", json=second_payload, headers=SECURE_HEADERS)

    assert first_response.status_code == 201
    assert second_response.status_code == 409
    assert second_response.json()["detail"]["message"] == (
        "Se detectó una transacción duplicada en menos de 2 segundos."
    )


def test_create_payment_rejects_reused_idempotency_key(client):
    payload = _payload()

    first_response = client.post("/api/v1/payments/charges", json=payload, headers=SECURE_HEADERS)

    retry_payload = _payload(token="pm_tok_mastercard_ok")
    retry_payload["reservation_id"] = payload["reservation_id"]
    retry_payload["traveler_id"] = payload["traveler_id"]
    retry_payload["amount_in_cents"] = payload["amount_in_cents"]
    retry_payload["currency"] = payload["currency"]
    retry_payload["idempotency_key"] = payload["idempotency_key"]

    second_response = client.post(
        "/api/v1/payments/charges",
        json=retry_payload,
        headers=SECURE_HEADERS,
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 409
    assert second_response.json()["detail"]["message"] == "Se reutilizó una idempotency_key ya registrada."


def test_create_payment_rejects_invalid_checksum(client):
    payload = _payload()
    payload["request_checksum"] = "b" * 64

    response = client.post("/api/v1/payments/charges", json=payload, headers=SECURE_HEADERS)

    assert response.status_code == 400
    assert response.json() == {"detail": "Checksum de integridad inválido."}


def test_create_payment_accepts_valid_checksum(client):
    payload = _payload()
    canonical_payload = "|".join(
        [
            payload["reservation_id"],
            payload["traveler_id"],
            str(payload["amount_in_cents"]),
            payload["currency"].upper(),
            payload["payment_method_token"],
            payload["idempotency_key"],
        ]
    )
    payload["request_checksum"] = build_request_checksum(
        canonical_payload,
        settings.payment_integrity_secret,
    )

    response = client.post("/api/v1/payments/charges", json=payload, headers=SECURE_HEADERS)

    assert response.status_code == 201


def test_get_payment_by_id_returns_created_payment(client):
    create_response = client.post("/api/v1/payments/charges", json=_payload(), headers=SECURE_HEADERS)
    payment_id = create_response.json()["payment_id"]

    response = client.get(f"/api/v1/payments/{payment_id}")

    assert response.status_code == 200
    assert response.json()["payment_id"] == payment_id


def test_list_events_returns_created_events(client):
    create_response = client.post("/api/v1/payments/charges", json=_payload(), headers=SECURE_HEADERS)
    payment_id = create_response.json()["payment_id"]

    response = client.get(f"/api/v1/payments/{payment_id}/events")

    assert response.status_code == 200
    assert len(response.json()) == 4


def test_list_events_returns_404_for_unknown_payment(client):
    response = client.get(f"/api/v1/payments/{uuid4()}/events")

    assert response.status_code == 404
    assert response.json() == {"detail": "Pago no encontrado."}


def test_tls_header_can_be_enforced(client, monkeypatch):
    monkeypatch.setattr(
        payments_router,
        "settings",
        SimpleNamespace(enforce_tls_header=True),
    )

    response = client.post("/api/v1/payments/charges", json=_payload())

    assert response.status_code == 400
    assert response.json() == {"detail": "TLS 1.2+ is required for payment requests"}

    secure_response = client.post(
        "/api/v1/payments/charges",
        json=_payload(),
        headers={"x-forwarded-proto": "https"},
    )
    assert secure_response.status_code == 201

    monkeypatch.setattr(
        payments_router,
        "settings",
        settings,
    )


def test_cors_allows_frontend_origin(client):
    response = client.options(
        "/api/v1/payments/charges",
        headers={
            "origin": "http://localhost:3000",
            "access-control-request-method": "POST",
            "access-control-request-headers": "content-type,x-forwarded-proto",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_get_payments_config_returns_current_provider(client):
    response = client.get("/api/v1/payments/config")

    assert response.status_code == 200
    body = response.json()
    assert body["provider"] in {"fake_stripe", "stripe_test"}
    assert "stripe_enabled" in body
    assert "publishable_key" in body


def test_create_checkout_session_returns_transaction_metadata(client, monkeypatch):
    monkeypatch.setenv("PAYMENT_PROVIDER", "stripe_test")
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_example")
    monkeypatch.setenv("STRIPE_PUBLISHABLE_KEY", "pk_test_example")

    response = client.post(
        "/api/v1/payments/create-intent",
        json=_checkout_payload(),
        headers=SECURE_HEADERS,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["currency"] == "COP"
    assert body["provider_code"] == "stripe_test"
    assert body["stripe_enabled"] is True
    assert body["publishable_key"] == "pk_test_example"


def test_create_charge_is_disabled_when_provider_is_not_fake_stripe(client, monkeypatch):
    monkeypatch.setenv("PAYMENT_PROVIDER", "stripe_test")

    response = client.post("/api/v1/payments/charges", json=_payload(), headers=SECURE_HEADERS)

    assert response.status_code == 400
    assert "PAYMENT_PROVIDER=fake_stripe" in response.json()["detail"]


def test_finalize_stripe_payment_materializes_confirmed_payment(client, test_engine, monkeypatch):
    monkeypatch.setenv("PAYMENT_PROVIDER", "stripe_test")
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_example")
    monkeypatch.setenv("STRIPE_PUBLISHABLE_KEY", "pk_test_example")
    gateway = FakeStripeCheckoutGateway(finalize_status="succeeded")
    dispatcher = FakeNotificationDispatcher()
    client.app.dependency_overrides[get_stripe_checkout_gateway] = lambda: gateway
    client.app.dependency_overrides[get_notification_dispatcher] = lambda: dispatcher
    client.app.dependency_overrides[get_payment_processing_runner] = lambda: (
        InProcessPaymentProcessingRunner(
            session_factory=lambda: Session(test_engine),
            gateway=gateway,
            notification_dispatcher=dispatcher,
            reservation_updater=FakeReservationUpdater(),
        )
    )

    create_response = client.post(
        "/api/v1/payments/create-intent",
        json=_checkout_payload(),
        headers=SECURE_HEADERS,
    )
    transaction_id = create_response.json()["payment_transaction_id"]

    finalize_response = client.post(
        "/api/v1/payments/finalize",
        json={
            "payment_transaction_id": transaction_id,
            "confirmation_token_id": "ctoken_test_123",
        },
        headers=SECURE_HEADERS,
    )

    assert finalize_response.status_code == 202
    body = finalize_response.json()
    assert body["status"] == "pending"
    assert body["payment_id"] is not None

    with Session(test_engine) as session:
        stored_session = session.exec(select(PaymentCheckoutSession)).first()
        stored_payment = session.exec(select(Payment)).first()
        stored_audit_logs = session.exec(select(PaymentAuditLog)).all()
        processing_item = session.exec(select(PaymentProcessingOutbox)).first()

    assert stored_session is not None
    assert stored_session.status == "confirmed"
    assert stored_session.confirmation_token_id is not None
    assert stored_session.confirmation_token_id.startswith("enc:v1:")
    assert stored_session.confirmation_token_id != "ctoken_test_123"
    assert stored_session.client_secret is not None
    assert stored_session.client_secret.startswith("enc:v1:")
    assert stored_payment is not None
    assert stored_payment.gateway_charge_id == "pi_test_123"
    assert stored_payment.status == "confirmed"
    assert stored_payment.receipt_number is not None
    assert processing_item is not None
    assert processing_item.status == "succeeded"
    assert len(dispatcher.calls) == 1
    assert str(dispatcher.calls[0]["payment_id"]) == body["payment_id"]
    confirmed_audit = next(
        log for log in stored_audit_logs if log.action == "payment.processing.confirmed"
    )
    assert confirmed_audit.payload["amount_in_cents"] == 287650
    accepted_audit = next(
        log for log in stored_audit_logs if log.action == "payment.finalize.accepted"
    )
    assert accepted_audit.payload["currency"] == "COP"


def test_get_payment_confirmation_returns_checkout_summary(client, test_engine, monkeypatch):
    monkeypatch.setenv("PAYMENT_PROVIDER", "stripe_test")
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_example")
    monkeypatch.setenv("STRIPE_PUBLISHABLE_KEY", "pk_test_example")
    gateway = FakeStripeCheckoutGateway(finalize_status="succeeded")
    client.app.dependency_overrides[get_stripe_checkout_gateway] = lambda: gateway
    client.app.dependency_overrides[get_payment_processing_runner] = lambda: (
        InProcessPaymentProcessingRunner(
            session_factory=lambda: Session(test_engine),
            gateway=gateway,
            notification_dispatcher=FakeNotificationDispatcher(),
            reservation_updater=FakeReservationUpdater(),
        )
    )

    create_response = client.post(
        "/api/v1/payments/create-intent",
        json=_checkout_payload(),
        headers=SECURE_HEADERS,
    )
    transaction_id = create_response.json()["payment_transaction_id"]

    finalize_response = client.post(
        "/api/v1/payments/finalize",
        json={
            "payment_transaction_id": transaction_id,
            "confirmation_token_id": "ctoken_test_confirmation",
        },
        headers=SECURE_HEADERS,
    )

    assert finalize_response.status_code == 202
    payment_id = finalize_response.json()["payment_id"]
    response = client.get(f"/api/v1/payments/{payment_id}/confirmation")

    assert response.status_code == 200
    body = response.json()
    assert body["payment_id"] == payment_id
    assert body["property_name"] == "Renaissance Estate"
    assert body["check_in_date"] == "2026-10-12"
    assert body["check_out_date"] == "2026-10-17"
    assert body["receipt_number"] is not None


def test_webhook_can_complete_requires_action_checkout(client, test_engine, monkeypatch):
    monkeypatch.setenv("PAYMENT_PROVIDER", "stripe_test")
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_example")
    monkeypatch.setenv("STRIPE_PUBLISHABLE_KEY", "pk_test_example")
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_test")
    gateway = FakeStripeCheckoutGateway(finalize_status="requires_action")
    client.app.dependency_overrides[get_stripe_checkout_gateway] = lambda: gateway
    client.app.dependency_overrides[get_payment_processing_runner] = lambda: (
        InProcessPaymentProcessingRunner(
            session_factory=lambda: Session(test_engine),
            gateway=gateway,
            notification_dispatcher=FakeNotificationDispatcher(),
            reservation_updater=FakeReservationUpdater(),
        )
    )

    create_response = client.post(
        "/api/v1/payments/create-intent",
        json=_checkout_payload(),
        headers=SECURE_HEADERS,
    )
    transaction_id = create_response.json()["payment_transaction_id"]

    finalize_response = client.post(
        "/api/v1/payments/finalize",
        json={
            "payment_transaction_id": transaction_id,
            "confirmation_token_id": "ctoken_test_requires_action",
        },
        headers=SECURE_HEADERS,
    )

    assert finalize_response.status_code == 202
    assert finalize_response.json()["status"] == "pending"

    status_response = client.get(f"/api/v1/payments/checkout/{transaction_id}")
    assert status_response.status_code == 200
    assert status_response.json()["status"] == "requires_action"

    webhook_response = client.post(
        "/api/v1/payments/webhook",
        content=b'{"type":"payment_intent.succeeded"}',
        headers={"Stripe-Signature": "test-signature"},
    )

    assert webhook_response.status_code == 200

    status_response = client.get(f"/api/v1/payments/checkout/{transaction_id}")
    assert status_response.status_code == 200
    assert status_response.json()["status"] == "confirmed"

    with Session(test_engine) as session:
        stored_payment = session.exec(select(Payment)).first()
        stored_audit_logs = session.exec(select(PaymentAuditLog)).all()

    assert stored_payment is not None
    assert stored_payment.status == "confirmed"
    webhook_audit = next(log for log in stored_audit_logs if log.action == "payment.webhook.processed")
    assert webhook_audit.payload["amount_in_cents"] == 287650
    assert webhook_audit.payload["currency"] == "COP"


def test_finalize_stripe_payment_returns_failed_response_for_card_error(client, test_engine, monkeypatch):
    monkeypatch.setenv("PAYMENT_PROVIDER", "stripe_test")
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_example")
    monkeypatch.setenv("STRIPE_PUBLISHABLE_KEY", "pk_test_example")
    gateway = FakeStripeCheckoutGateway(finalize_status="card_error")
    client.app.dependency_overrides[get_stripe_checkout_gateway] = lambda: gateway
    client.app.dependency_overrides[get_payment_processing_runner] = lambda: (
        InProcessPaymentProcessingRunner(
            session_factory=lambda: Session(test_engine),
            gateway=gateway,
            notification_dispatcher=FakeNotificationDispatcher(),
            reservation_updater=FakeReservationUpdater(),
        )
    )

    create_response = client.post(
        "/api/v1/payments/create-intent",
        json=_checkout_payload(),
        headers=SECURE_HEADERS,
    )
    transaction_id = create_response.json()["payment_transaction_id"]

    finalize_response = client.post(
        "/api/v1/payments/finalize",
        json={
            "payment_transaction_id": transaction_id,
            "confirmation_token_id": "ctoken_test_failed",
        },
        headers=SECURE_HEADERS,
    )

    assert finalize_response.status_code == 202
    body = finalize_response.json()
    assert body["status"] == "pending"
    assert body["payment_id"] is not None

    with Session(test_engine) as session:
        stored_payment = session.exec(select(Payment)).first()

    assert stored_payment is not None
    assert stored_payment.status == "failed"
    assert stored_payment.failure_reason == "card_declined"


def test_finalize_stripe_payment_returns_failed_response_for_insufficient_funds(client, test_engine, monkeypatch):
    monkeypatch.setenv("PAYMENT_PROVIDER", "stripe_test")
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_example")
    monkeypatch.setenv("STRIPE_PUBLISHABLE_KEY", "pk_test_example")
    gateway = FakeStripeCheckoutGateway(finalize_status="card_error_insufficient")
    client.app.dependency_overrides[get_stripe_checkout_gateway] = lambda: gateway
    client.app.dependency_overrides[get_payment_processing_runner] = lambda: (
        InProcessPaymentProcessingRunner(
            session_factory=lambda: Session(test_engine),
            gateway=gateway,
            notification_dispatcher=FakeNotificationDispatcher(),
            reservation_updater=FakeReservationUpdater(),
        )
    )

    create_response = client.post(
        "/api/v1/payments/create-intent",
        json=_checkout_payload(),
        headers=SECURE_HEADERS,
    )
    transaction_id = create_response.json()["payment_transaction_id"]

    finalize_response = client.post(
        "/api/v1/payments/finalize",
        json={
            "payment_transaction_id": transaction_id,
            "confirmation_token_id": "ctoken_test_insufficient",
        },
        headers=SECURE_HEADERS,
    )

    assert finalize_response.status_code == 202
    body = finalize_response.json()
    assert body["status"] == "pending"
    assert body["payment_id"] is not None

    with Session(test_engine) as session:
        stored_payment = session.exec(select(Payment)).first()

    assert stored_payment is not None
    assert stored_payment.status == "failed"
    assert stored_payment.failure_reason == "insufficient_funds"
