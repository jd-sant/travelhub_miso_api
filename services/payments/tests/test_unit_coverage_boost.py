from __future__ import annotations

from datetime import date, datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest

from adapters.gateways.stripe_checkout_gateway import StripeSdkCheckoutGateway
from adapters.services.notification_dispatcher import HttpNotificationDispatcher
from adapters.services.reservation_updater import HttpReservationUpdater
from core.security import decrypt_sensitive_value, encrypt_sensitive_value, sanitize_sensitive_data, verify_checksum
from domain.schemas.checkout import PaymentCheckoutSessionRecord, PaymentFinalizeRequest
from domain.schemas.payment import PaymentChargeResponse, PaymentStatus
from domain.use_cases.finalize_stripe_payment import FinalizeStripePaymentUseCase
from domain.use_cases.handle_stripe_webhook import HandleStripeWebhookUseCase
from errors import (
    PaymentCheckoutSessionNotFoundError,
    StripeConfigurationError,
    StripeIdempotencyConflictError,
    StripeWebhookVerificationError,
)


class _CheckoutRepo:
    def __init__(self, session: PaymentCheckoutSessionRecord | None):
        self.session = session
        self.updated = None

    def create_session(self, session):
        return session

    def get_session(self, _payment_transaction_id):
        return self.session

    def get_session_by_payment_intent(self, payment_intent_id: str):
        if self.session and self.session.payment_intent_id == payment_intent_id:
            return self.session
        return None

    def get_session_by_payment_id(self, _payment_id):
        return self.session

    def update_session(self, session):
        self.updated = session
        self.session = session
        return session


class _PaymentRepo:
    def __init__(self):
        self.saved = []
        self.events = []
        self.outbox_failures = []
        self.by_gateway = None

    def find_by_idempotency_key(self, _idempotency_key):
        return None

    def find_recent_duplicate(self, **_kwargs):
        return None

    def save_payment_result(self, payment):
        self.saved.append(payment)
        return payment

    def get_by_id(self, _payment_id):
        return self.saved[-1] if self.saved else None

    def find_by_gateway_charge_id(self, _gateway_charge_id):
        return self.by_gateway

    def add_events(self, payment_id, events):
        self.events.append((payment_id, events))

    def list_events(self, _payment_id):
        return []

    def upsert_reservation_confirmation_outbox_failure(self, **kwargs):
        self.outbox_failures.append(kwargs)

    def list_due_reservation_confirmation_outbox(self, **_kwargs):
        return []

    def mark_reservation_confirmation_outbox_succeeded(self, **_kwargs):
        return None

    def mark_reservation_confirmation_outbox_retry(self, **_kwargs):
        return None

    def count_reservation_confirmation_outbox_pending(self, **_kwargs):
        return 0


class _AuditRepo:
    def __init__(self):
        self.logs = []

    def add_log(self, record):
        self.logs.append(record)


class _Gateway:
    def __init__(self, intent=None, err=None):
        self.intent = intent or {"id": "pi_test_1", "status": "succeeded", "client_secret": "cs"}
        self.err = err

    def create_and_confirm_payment(self, **_kwargs):
        if self.err:
            raise self.err
        return self.intent

    def construct_event(self, *, payload: bytes, signature: str):
        if signature != "sig-ok":
            raise ValueError("bad signature")
        return {
            "type": "payment_intent.succeeded",
            "data": {
                "object": {
                    "id": "pi_webhook",
                }
            },
        }


class _NotificationDispatcher:
    def __init__(self, fail=False):
        self.fail = fail
        self.calls = 0

    def dispatch_payment_confirmation(self, *, payment_id, source_ip=None):
        self.calls += 1
        if self.fail:
            raise RuntimeError("notifications down")


class _ReservationUpdater:
    def __init__(self, fail=False):
        self.fail = fail
        self.calls = 0

    def confirm_reservation(self, *, reservation_id, source_ip=None):
        self.calls += 1
        if self.fail:
            raise RuntimeError("reservations down")


def _session_record() -> PaymentCheckoutSessionRecord:
    now = datetime.now(timezone.utc)
    return PaymentCheckoutSessionRecord(
        payment_transaction_id=uuid4(),
        reservation_id=uuid4(),
        traveler_id=uuid4(),
        provider_code="stripe_test",
        amount_in_cents=120000,
        currency="COP",
        property_name="Hotel",
        check_in_date=date(2026, 4, 12),
        check_out_date=date(2026, 4, 15),
        idempotency_key="idemp-1234",
        confirmation_token_id=None,
        payment_intent_id="pi_webhook",
        status="pending",
        payment_id=None,
        client_secret=None,
        error=None,
        created_at=now,
        updated_at=now,
    )


def _use_case(monkeypatch, session: PaymentCheckoutSessionRecord | None, gateway=None):
    monkeypatch.setattr(
        "domain.use_cases.finalize_stripe_payment.settings",
        SimpleNamespace(
            stripe_enabled=True,
            payment_duplicate_window_seconds=2,
            payment_integrity_secret="secret",
            reservation_confirmation_retry_max_attempts=5,
        ),
    )
    checkout_repo = _CheckoutRepo(session)
    payment_repo = _PaymentRepo()
    audit_repo = _AuditRepo()
    use_case = FinalizeStripePaymentUseCase(
        checkout_repository=checkout_repo,
        payment_repository=payment_repo,
        audit_repository=audit_repo,
        gateway=gateway or _Gateway(),
        notification_dispatcher=_NotificationDispatcher(),
        reservation_updater=_ReservationUpdater(),
    )
    return use_case, checkout_repo, payment_repo, audit_repo


def test_finalize_raises_when_stripe_not_configured(monkeypatch):
    monkeypatch.setattr(
        "domain.use_cases.finalize_stripe_payment.settings",
        SimpleNamespace(stripe_enabled=False),
    )
    use_case = FinalizeStripePaymentUseCase(_CheckoutRepo(_session_record()), _PaymentRepo(), _AuditRepo(), _Gateway(), _NotificationDispatcher(), _ReservationUpdater())
    with pytest.raises(StripeConfigurationError):
        use_case.execute(PaymentFinalizeRequest(payment_transaction_id=uuid4(), confirmation_token_id="tok"))


def test_finalize_raises_when_checkout_session_not_found(monkeypatch):
    use_case, *_ = _use_case(monkeypatch, None)
    with pytest.raises(PaymentCheckoutSessionNotFoundError):
        use_case.execute(PaymentFinalizeRequest(payment_transaction_id=uuid4(), confirmation_token_id="tok"))


def test_finalize_returns_existing_session_when_payment_already_created(monkeypatch):
    session = _session_record()
    session.payment_id = uuid4()
    session.status = "confirmed"

    use_case, *_ = _use_case(monkeypatch, session)
    response = use_case.execute(
        PaymentFinalizeRequest(
            payment_transaction_id=session.payment_transaction_id,
            confirmation_token_id="tok",
        )
    )

    assert response.status == "confirmed"
    assert response.payment_id == session.payment_id


def test_finalize_handles_idempotency_conflict(monkeypatch):
    session = _session_record()
    gateway = _Gateway(err=StripeIdempotencyConflictError("dup"))
    use_case, *_ = _use_case(monkeypatch, session, gateway=gateway)

    response = use_case.execute(
        PaymentFinalizeRequest(
            payment_transaction_id=session.payment_transaction_id,
            confirmation_token_id="tok",
        )
    )

    assert response.error is not None
    assert "Duplicate" in response.error


def test_finalize_dispatch_failures_are_audited_and_queued(monkeypatch):
    session = _session_record()
    monkeypatch.setattr(
        "domain.use_cases.finalize_stripe_payment.settings",
        SimpleNamespace(
            stripe_enabled=True,
            payment_duplicate_window_seconds=2,
            payment_integrity_secret="secret",
            reservation_confirmation_retry_max_attempts=3,
        ),
    )
    checkout_repo = _CheckoutRepo(session)
    payment_repo = _PaymentRepo()
    audit_repo = _AuditRepo()
    use_case = FinalizeStripePaymentUseCase(
        checkout_repository=checkout_repo,
        payment_repository=payment_repo,
        audit_repository=audit_repo,
        gateway=_Gateway(intent={"id": "pi_2", "status": "succeeded", "client_secret": "cs"}),
        notification_dispatcher=_NotificationDispatcher(fail=True),
        reservation_updater=_ReservationUpdater(fail=True),
    )

    response = use_case.execute(
        PaymentFinalizeRequest(
            payment_transaction_id=session.payment_transaction_id,
            confirmation_token_id="tok_2",
        )
    )

    assert response.status == "confirmed"
    assert len(payment_repo.outbox_failures) == 1
    actions = {log.action for log in audit_repo.logs}
    assert "notification.payment_confirmation.dispatch_failed" in actions
    assert "reservation.confirmation.dispatch_failed" in actions


def test_handle_webhook_verification_and_existing_payment_paths(monkeypatch):
    monkeypatch.setattr(
        "domain.use_cases.handle_stripe_webhook.settings",
        SimpleNamespace(
            payment_duplicate_window_seconds=2,
            payment_integrity_secret="secret",
            reservation_confirmation_retry_max_attempts=3,
        ),
    )
    session = _session_record()
    checkout_repo = _CheckoutRepo(session)
    payment_repo = _PaymentRepo()
    audit_repo = _AuditRepo()
    gateway = _Gateway()

    use_case = HandleStripeWebhookUseCase(
        checkout_repository=checkout_repo,
        payment_repository=payment_repo,
        audit_repository=audit_repo,
        gateway=gateway,
        notification_dispatcher=_NotificationDispatcher(),
        reservation_updater=_ReservationUpdater(),
    )

    with pytest.raises(StripeWebhookVerificationError):
        use_case.execute((b"{}", "invalid"))

    existing_payment = PaymentChargeResponse(
        payment_id=uuid4(),
        reservation_id=session.reservation_id,
        traveler_id=session.traveler_id,
        provider_code=session.provider_code,
        status=PaymentStatus.confirmed,
        amount_in_cents=session.amount_in_cents,
        currency=session.currency,
        gateway_charge_id=session.payment_intent_id or "",
        gateway_status="succeeded",
        idempotency_key=session.idempotency_key,
        request_fingerprint="fp",
        duplicate_guard_key="dg",
        request_checksum="cs",
        payment_method_token_hash="ht",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    payment_repo.by_gateway = existing_payment

    use_case.execute((b"{}", "sig-ok"), source_ip="127.0.0.1")
    assert checkout_repo.updated is not None
    assert checkout_repo.updated.payment_id == existing_payment.payment_id


def test_security_helpers_cover_encryption_checksum_and_redaction():
    payload = "reservation|traveler|120000|COP|token|idemp"
    secret = "my-secret"
    checksum = verify_checksum(payload=payload, expected_checksum="x" * 64, secret=secret)
    assert checksum is False

    encrypted = encrypt_sensitive_value("tok_123", secret)
    assert encrypted is not None and encrypted.startswith("enc:v1:")
    assert decrypt_sensitive_value(encrypted, secret) == "tok_123"
    assert decrypt_sensitive_value("plain", secret) == "plain"

    sanitized = sanitize_sensitive_data(
        {"card_number": "4242424242424242", "nested": ["5500000000000004", "ok"]}
    )
    assert sanitized["card_number"] == "[REDACTED]"
    assert sanitized["nested"][0] == "[REDACTED]"


def test_http_dispatchers_cover_no_url_and_success(monkeypatch):
    called = {"post": 0, "patch": 0}

    class _OkResponse:
        @staticmethod
        def raise_for_status():
            return None

    monkeypatch.setattr(
        "adapters.services.notification_dispatcher.settings",
        SimpleNamespace(notifications_service_url="", internal_api_key="k"),
    )
    HttpNotificationDispatcher().dispatch_payment_confirmation(payment_id=uuid4(), source_ip="127.0.0.1")

    monkeypatch.setattr(
        "adapters.services.reservation_updater.settings",
        SimpleNamespace(reservations_service_url="", internal_api_key="k"),
    )
    HttpReservationUpdater().confirm_reservation(reservation_id=uuid4(), source_ip="127.0.0.1")

    monkeypatch.setattr(
        "adapters.services.notification_dispatcher.settings",
        SimpleNamespace(notifications_service_url="http://notifications:8000", internal_api_key="k"),
    )
    monkeypatch.setattr(
        "adapters.services.reservation_updater.settings",
        SimpleNamespace(reservations_service_url="http://reservations:8000", internal_api_key="k"),
    )

    def _post(*_args, **_kwargs):
        called["post"] += 1
        return _OkResponse()

    def _patch(*_args, **_kwargs):
        called["patch"] += 1
        return _OkResponse()

    monkeypatch.setattr(httpx, "post", _post)
    monkeypatch.setattr(httpx, "patch", _patch)

    HttpNotificationDispatcher().dispatch_payment_confirmation(payment_id=uuid4(), source_ip="10.0.0.1")
    HttpReservationUpdater().confirm_reservation(reservation_id=uuid4(), source_ip="10.0.0.1")

    assert called == {"post": 1, "patch": 1}


def test_stripe_gateway_extract_card_error_payload_branches():
    gateway = StripeSdkCheckoutGateway.__new__(StripeSdkCheckoutGateway)

    class _ErrorObj:
        code = "card_declined"
        decline_code = "insufficient_funds"
        message = "declined"

    class _ExcA:
        error = _ErrorObj()
        json_body = None

    payload_a = gateway._extract_card_error_payload(_ExcA())
    assert payload_a["decline_code"] == "insufficient_funds"

    class _ExcB:
        error = None
        json_body = {"error": {"code": "x", "decline_code": "y", "message": "z"}}

    payload_b = gateway._extract_card_error_payload(_ExcB())
    assert payload_b == {"code": "x", "decline_code": "y", "message": "z"}
