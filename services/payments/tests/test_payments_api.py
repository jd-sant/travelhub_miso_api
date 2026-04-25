import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import event, text
from sqlmodel import SQLModel, Session, create_engine, select

from adapters.models.payment_audit_log import PaymentAuditLog
from adapters.models.payment_checkout_session import PaymentCheckoutSession
from adapters.models.payment import Payment
from adapters.models.payment_event import PaymentEvent
from adapters.models.payment_refund import PaymentRefund
from adapters.models.payment_reservation_confirmation_outbox import (
    PaymentReservationConfirmationOutbox,
)
from assembly import (
    get_notification_dispatcher,
    get_refund_gateway,
    get_reservation_updater,
    get_stripe_checkout_gateway,
)
from core.config import settings
from core.security import build_request_checksum, hash_token
from db.session import get_session
from entrypoints.api.main import create_application
from entrypoints.api.routers import payments as payments_router
from errors import StripeIdempotencyConflictError, StripePaymentFailureError


SECURE_HEADERS = {"x-forwarded-proto": "https"}


class FakeStripeCheckoutGateway:
    def __init__(self, finalize_status: str = "succeeded"):
        self.finalize_status = finalize_status
        self.last_payment_intent_id = "pi_test_123"

    def create_and_confirm_payment(self, **kwargs):
        if self.finalize_status == "card_error":
            raise StripePaymentFailureError(code="card_declined", message="Your card was declined.")
        if self.finalize_status == "card_error_insufficient":
            raise StripePaymentFailureError(code="insufficient_funds", message="Your card has insufficient funds.")
        if self.finalize_status == "idempotency_error":
            raise StripeIdempotencyConflictError("Duplicate Stripe confirmation attempt.")
        if self.finalize_status == "requires_action":
            return {
                "id": self.last_payment_intent_id,
                "status": "requires_action",
                "client_secret": "pi_test_123_secret_abc",
            }
        if self.finalize_status == "failed":
            return {
                "id": self.last_payment_intent_id,
                "status": "requires_payment_method",
                "client_secret": "pi_test_123_secret_abc",
                "last_payment_error": {
                    "code": "card_declined",
                    "message": "Your card was declined.",
                },
            }
        return {
            "id": self.last_payment_intent_id,
            "status": "succeeded",
            "client_secret": "pi_test_123_secret_abc",
        }

    def construct_event(self, *, payload: bytes, signature: str):
        if signature != "test-signature":
            raise ValueError("invalid signature")
        return {
            "type": "payment_intent.succeeded",
            "data": {
                "object": {
                    "id": self.last_payment_intent_id,
                }
            },
        }


class FakeNotificationDispatcher:
    def __init__(self, should_fail: bool = False):
        self.should_fail = should_fail
        self.calls = []

    def dispatch_payment_confirmation(self, *, payment_id, source_ip=None):
        self.calls.append({"payment_id": payment_id, "source_ip": source_ip})
        if self.should_fail:
            raise RuntimeError("notifications unavailable")


class FakeReservationUpdater:
    def __init__(self, should_fail: bool = False):
        self.should_fail = should_fail
        self.calls = []
        self.refund_result_calls = []
        self.additional_charge_result_calls = []

    def confirm_reservation(self, *, reservation_id, source_ip=None):
        self.calls.append({"reservation_id": reservation_id, "source_ip": source_ip})
        if self.should_fail:
            raise RuntimeError("reservations unavailable")

    def notify_refund_result(
        self,
        *,
        reservation_id,
        status,
        amount_in_cents,
        refund_id,
        source_ip=None,
    ):
        self.refund_result_calls.append(
            {
                "reservation_id": reservation_id,
                "status": status,
                "amount_in_cents": amount_in_cents,
                "refund_id": refund_id,
            }
        )
        if self.should_fail:
            raise RuntimeError("reservations unavailable")

    def notify_additional_charge_result(
        self,
        *,
        reservation_id,
        status,
        amount_in_cents,
        payment_id,
        source_ip=None,
    ):
        self.additional_charge_result_calls.append(
            {
                "reservation_id": reservation_id,
                "status": status,
                "amount_in_cents": amount_in_cents,
                "payment_id": payment_id,
            }
        )
        if self.should_fail:
            raise RuntimeError("reservations unavailable")


class FailingRefundGateway:
    def process_refund(self, *, reason: str) -> None:
        _ = reason
        raise RuntimeError("Refund gateway unavailable")


def _build_app(test_engine):
    app = create_application()

    def override_get_session():
        with Session(test_engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    return app


@pytest.fixture(scope="function")
def test_engine():
    database_url = os.getenv("PAYMENTS_TEST_DATABASE_URL")
    if database_url:
        schema_name = f"payments_test_{uuid4().hex}"
        engine = create_engine(database_url)

        @event.listens_for(engine, "connect")
        def _set_search_path(dbapi_connection, _connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute(f"SET search_path TO {schema_name}, public")
            cursor.close()
            dbapi_connection.commit()

        with engine.connect() as conn:
            conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema_name}"))
            conn.commit()
        SQLModel.metadata.create_all(engine)
        yield engine
        SQLModel.metadata.drop_all(engine)
        with engine.connect() as conn:
            conn.execute(text(f"DROP SCHEMA IF EXISTS {schema_name} CASCADE"))
            conn.commit()
        engine.dispose()
        return

    db_file = Path(__file__).resolve().parent / "payments_test.db"
    if db_file.exists():
        db_file.unlink()
    engine = create_engine(
        f"sqlite:///{db_file}",
        connect_args={"check_same_thread": False},
    )
    SQLModel.metadata.create_all(engine)
    yield engine
    engine.dispose()
    if db_file.exists():
        db_file.unlink()


@pytest.fixture
def client(test_engine):
    previous_skip_flag = os.environ.get("SKIP_DB_INIT_ON_STARTUP")
    os.environ["SKIP_DB_INIT_ON_STARTUP"] = "true"

    with Session(test_engine) as session:
        for audit_log in session.exec(select(PaymentAuditLog)).all():
            session.delete(audit_log)
        for outbox_item in session.exec(select(PaymentReservationConfirmationOutbox)).all():
            session.delete(outbox_item)
        for checkout_session in session.exec(select(PaymentCheckoutSession)).all():
            session.delete(checkout_session)
        for event in session.exec(select(PaymentEvent)).all():
            session.delete(event)
        for refund in session.exec(select(PaymentRefund)).all():
            session.delete(refund)
        for payment in session.exec(select(Payment)).all():
            session.delete(payment)
        session.commit()

    app = _build_app(test_engine)
    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
    if previous_skip_flag is None:
        os.environ.pop("SKIP_DB_INIT_ON_STARTUP", None)
    else:
        os.environ["SKIP_DB_INIT_ON_STARTUP"] = previous_skip_flag


def _payload(token: str = "pm_tok_visa_ok") -> dict:
    return {
        "reservation_id": str(uuid4()),
        "traveler_id": str(uuid4()),
        "payment_method_token": token,
        "amount_in_cents": 125000,
        "currency": "cop",
        "idempotency_key": "booking-123-attempt-1",
    }


def _checkout_payload() -> dict:
    return {
        "reservation_id": str(uuid4()),
        "traveler_id": str(uuid4()),
        "amount_in_cents": 287650,
        "currency": "cop",
        "property_name": "Renaissance Estate",
        "check_in_date": "2026-10-12",
        "check_out_date": "2026-10-17",
    }


def _refund_payload(payment_id: str, *, reason: str = "traveler_request") -> dict:
    return {
        "payment_id": payment_id,
        "amount_in_cents": 50000,
        "reason": reason,
        "idempotency_key": f"refund-{uuid4()}",
    }


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

    assert finalize_response.status_code == 200
    body = finalize_response.json()
    assert body["status"] == "confirmed"
    assert body["payment_id"] is not None
    assert body["payment_intent_id"] == "pi_test_123"

    with Session(test_engine) as session:
        stored_session = session.exec(select(PaymentCheckoutSession)).first()
        stored_payment = session.exec(select(Payment)).first()
        stored_audit_logs = session.exec(select(PaymentAuditLog)).all()

    assert stored_session is not None
    assert stored_session.status == "confirmed"
    assert stored_session.confirmation_token_id is not None
    assert stored_session.confirmation_token_id.startswith("enc:v1:")
    assert stored_session.confirmation_token_id != "ctoken_test_123"
    assert stored_session.client_secret is not None
    assert stored_session.client_secret.startswith("enc:v1:")
    assert stored_payment is not None
    assert stored_payment.gateway_charge_id == "pi_test_123"
    assert stored_payment.receipt_number is not None
    assert len(dispatcher.calls) == 1
    assert str(dispatcher.calls[0]["payment_id"]) == body["payment_id"]
    confirmed_audit = next(
        log for log in stored_audit_logs if log.action == "payment.finalize.confirmed"
    )
    assert confirmed_audit.payload["amount_in_cents"] == 287650
    assert confirmed_audit.payload["currency"] == "COP"


def test_get_payment_confirmation_returns_checkout_summary(client, monkeypatch):
    monkeypatch.setenv("PAYMENT_PROVIDER", "stripe_test")
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_example")
    monkeypatch.setenv("STRIPE_PUBLISHABLE_KEY", "pk_test_example")
    gateway = FakeStripeCheckoutGateway(finalize_status="succeeded")
    client.app.dependency_overrides[get_stripe_checkout_gateway] = lambda: gateway

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

    assert finalize_response.status_code == 200
    assert finalize_response.json()["status"] == "requires_action"

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

    assert finalize_response.status_code == 200
    body = finalize_response.json()
    assert body["status"] == "failed"
    assert body["payment_id"] is not None
    assert "declined" in body["error"].lower()

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

    assert finalize_response.status_code == 200
    body = finalize_response.json()
    assert body["status"] == "failed"
    assert body["payment_id"] is not None
    assert "insufficient" in body["error"].lower()

    with Session(test_engine) as session:
        stored_payment = session.exec(select(Payment)).first()

    assert stored_payment is not None
    assert stored_payment.status == "failed"
    assert stored_payment.failure_reason == "insufficient_funds"


def test_create_refund_returns_pending_status(client):
    payment_response = client.post("/api/v1/payments/charges", json=_payload(), headers=SECURE_HEADERS)
    payment_id = payment_response.json()["payment_id"]

    response = client.post(
        "/api/v1/payments/refunds",
        json=_refund_payload(payment_id),
        headers=SECURE_HEADERS,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["payment_id"] == payment_id
    assert body["status"] == "pending"
    assert body["retry_count"] == 0


def test_create_refund_records_correlation_id_and_metrics_audit(client, test_engine):
    payment_response = client.post("/api/v1/payments/charges", json=_payload(), headers=SECURE_HEADERS)
    payment_id = payment_response.json()["payment_id"]

    response = client.post(
        "/api/v1/payments/refunds",
        json=_refund_payload(payment_id),
        headers={**SECURE_HEADERS, "X-Correlation-Id": "corr-refund-123"},
    )

    assert response.status_code == 201

    with Session(test_engine) as session:
        stored_audit_logs = session.exec(select(PaymentAuditLog)).all()

    requested_log = next(
        log for log in stored_audit_logs if log.action == "payment.refund.requested"
    )
    metrics_log = next(
        log for log in stored_audit_logs if log.action == "payment.refund.metrics"
    )

    assert requested_log.payload["correlation_id"] == "corr-refund-123"
    assert metrics_log.payload["correlation_id"] == "corr-refund-123"
    assert metrics_log.payload["refund_latency_seconds"] >= 0
    assert metrics_log.payload["refund_sla_breach_count"] in {0, 1}


def test_create_refund_is_idempotent_for_same_key(client):
    payment_response = client.post("/api/v1/payments/charges", json=_payload(), headers=SECURE_HEADERS)
    payment_id = payment_response.json()["payment_id"]
    payload = _refund_payload(payment_id)

    first_response = client.post("/api/v1/payments/refunds", json=payload, headers=SECURE_HEADERS)
    second_response = client.post("/api/v1/payments/refunds", json=payload, headers=SECURE_HEADERS)

    assert first_response.status_code == 201
    assert second_response.status_code == 201
    assert first_response.json()["refund_id"] == second_response.json()["refund_id"]


def test_create_refund_rejects_failed_payment(client):
    failed_payment = client.post(
        "/api/v1/payments/charges",
        json=_payload(token="pm_fail_card_declined"),
        headers=SECURE_HEADERS,
    )
    payment_id = failed_payment.json()["payment_id"]

    response = client.post(
        "/api/v1/payments/refunds",
        json=_refund_payload(payment_id),
        headers=SECURE_HEADERS,
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Solo se permiten reembolsos para pagos confirmados."


def test_get_refund_returns_created_refund(client):
    payment_response = client.post("/api/v1/payments/charges", json=_payload(), headers=SECURE_HEADERS)
    payment_id = payment_response.json()["payment_id"]
    create_refund = client.post(
        "/api/v1/payments/refunds",
        json=_refund_payload(payment_id),
        headers=SECURE_HEADERS,
    )
    refund_id = create_refund.json()["refund_id"]

    response = client.get(f"/api/v1/payments/refunds/{refund_id}")

    assert response.status_code == 200
    assert response.json()["refund_id"] == refund_id


def test_get_refund_returns_404_for_unknown_refund(client):
    response = client.get(f"/api/v1/payments/refunds/{uuid4()}")

    assert response.status_code == 404
    assert response.json() == {"detail": "Reembolso no encontrado."}


def test_retry_payment_refunds_succeeds_pending_refund(client):
    updater = FakeReservationUpdater()
    client.app.dependency_overrides[get_reservation_updater] = lambda: updater

    payment_response = client.post("/api/v1/payments/charges", json=_payload(), headers=SECURE_HEADERS)
    payment_id = payment_response.json()["payment_id"]
    create_refund = client.post(
        "/api/v1/payments/refunds",
        json=_refund_payload(payment_id),
        headers=SECURE_HEADERS,
    )
    refund_id = create_refund.json()["refund_id"]

    retry_response = client.post(
        "/api/v1/internal/payments/refunds/retry",
        headers={"X-Internal-Api-Key": settings.internal_api_key},
    )

    assert retry_response.status_code == 200
    retry_body = retry_response.json()
    assert retry_body["processed_count"] == 1
    assert retry_body["succeeded_count"] == 1
    assert retry_body["failed_count"] == 0

    status_response = client.get(f"/api/v1/payments/refunds/{refund_id}")
    assert status_response.status_code == 200
    assert status_response.json()["status"] == "succeeded"
    assert len(updater.refund_result_calls) == 1
    assert updater.refund_result_calls[0]["status"] == "succeeded"


def test_retry_payment_refunds_requires_internal_api_key(client):
    response = client.post(
        "/api/v1/internal/payments/refunds/retry",
        headers={"X-Internal-Api-Key": "invalid-key"},
    )

    assert response.status_code == 403


def test_retry_payment_refunds_can_reach_terminal_failed(client, test_engine, monkeypatch):
    monkeypatch.setenv("REFUND_RETRY_MAX_ATTEMPTS", "2")
    monkeypatch.setenv("REFUND_RETRY_BASE_SECONDS", "1")
    client.app.dependency_overrides[get_refund_gateway] = lambda: FailingRefundGateway()
    payment_response = client.post("/api/v1/payments/charges", json=_payload(), headers=SECURE_HEADERS)
    payment_id = payment_response.json()["payment_id"]

    create_refund = client.post(
        "/api/v1/payments/refunds",
        json=_refund_payload(payment_id, reason="manual_refund_retry"),
        headers=SECURE_HEADERS,
    )
    refund_id = create_refund.json()["refund_id"]

    first_retry = client.post(
        "/api/v1/internal/payments/refunds/retry",
        headers={"X-Internal-Api-Key": settings.internal_api_key},
    )

    assert first_retry.status_code == 200
    assert first_retry.json()["failed_count"] == 1

    with Session(test_engine) as session:
        stored_refund = session.get(PaymentRefund, UUID(refund_id))
        assert stored_refund is not None
        stored_refund.next_retry_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        session.add(stored_refund)
        session.commit()

    second_retry = client.post(
        "/api/v1/internal/payments/refunds/retry",
        headers={"X-Internal-Api-Key": settings.internal_api_key},
    )

    assert second_retry.status_code == 200
    assert second_retry.json()["failed_count"] == 1

    final_status = client.get(f"/api/v1/payments/refunds/{refund_id}")
    assert final_status.status_code == 200
    assert final_status.json()["status"] == "failed"


def test_internal_create_refund_for_reservation_uses_latest_confirmed_payment(client):
    payment_response = client.post("/api/v1/payments/charges", json=_payload(), headers=SECURE_HEADERS)
    reservation_id = payment_response.json()["reservation_id"]

    response = client.post(
        "/api/v1/internal/payments/refunds",
        json={
            "reservation_id": reservation_id,
            "amount_in_cents": 40000,
            "reason": "traveler_request",
            "idempotency_key": f"int-refund-{uuid4()}",
        },
        headers={"X-Internal-Api-Key": settings.internal_api_key},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["reservation_id"] == reservation_id
    assert body["status"] == "pending"


def test_internal_additional_charge_endpoint_creates_charge(client):
    payload = _payload()
    response = client.post(
        "/api/v1/internal/payments/additional-charges",
        json={
            "reservation_id": payload["reservation_id"],
            "traveler_id": payload["traveler_id"],
            "amount_in_cents": 35000,
            "currency": payload["currency"],
            "idempotency_key": f"int-additional-{uuid4()}",
            "payment_method_token": payload["payment_method_token"],
        },
        headers={"X-Internal-Api-Key": settings.internal_api_key},
    )

    assert response.status_code == 201
    assert response.json()["status"] in {"confirmed", "failed"}
