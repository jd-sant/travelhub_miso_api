"""Shared fixtures, fakes and helpers for payments tests."""
from __future__ import annotations

import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

# Importing the model modules ensures their tables are registered on the
# SQLModel.metadata before `create_all` runs.
from adapters.models.payment import Payment  # noqa: F401
from adapters.models.payment_audit_log import PaymentAuditLog  # noqa: F401
from adapters.models.payment_checkout_session import PaymentCheckoutSession  # noqa: F401
from adapters.models.payment_event import PaymentEvent  # noqa: F401
from adapters.models.payment_processing_outbox import PaymentProcessingOutbox  # noqa: F401
from adapters.models.payment_reservation_confirmation_outbox import (  # noqa: F401
    PaymentReservationConfirmationOutbox,
)
from db.session import get_session
from entrypoints.api.main import create_application
from errors import StripeIdempotencyConflictError, StripePaymentFailureError


SECURE_HEADERS = {"x-forwarded-proto": "https"}


# --- Fakes -----------------------------------------------------------------


class FakeStripeCheckoutGateway:
    """Stripe checkout gateway double driven by a finalize_status flag."""

    def __init__(self, finalize_status: str = "succeeded"):
        self.finalize_status = finalize_status
        self.last_payment_intent_id = "pi_test_123"

    def create_and_confirm_payment(self, **kwargs):
        if self.finalize_status == "card_error":
            raise StripePaymentFailureError(
                code="card_declined", message="Your card was declined."
            )
        if self.finalize_status == "card_error_insufficient":
            raise StripePaymentFailureError(
                code="insufficient_funds",
                message="Your card has insufficient funds.",
            )
        if self.finalize_status == "idempotency_error":
            raise StripeIdempotencyConflictError(
                "Duplicate Stripe confirmation attempt."
            )
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
            "data": {"object": {"id": self.last_payment_intent_id}},
        }


class FakeNotificationDispatcher:
    def __init__(self, should_fail: bool = False):
        self.should_fail = should_fail
        self.calls: list[dict] = []

    def dispatch_payment_confirmation(self, *, payment_id, source_ip=None):
        self.calls.append({"payment_id": payment_id, "source_ip": source_ip})
        if self.should_fail:
            raise RuntimeError("notifications unavailable")


class FakeReservationUpdater:
    def __init__(self, should_fail: bool = False):
        self.should_fail = should_fail
        self.calls: list[dict] = []
        self.refund_result_calls: list[dict] = []
        self.additional_charge_result_calls: list[dict] = []

    def confirm_reservation(self, *, reservation_id, source_ip=None):
        self.calls.append(
            {"reservation_id": reservation_id, "source_ip": source_ip}
        )
        if self.should_fail:
            raise RuntimeError("reservations unavailable")

    def notify_refund_result(
        self, *, reservation_id, status, amount_in_cents, refund_id, source_ip=None
    ):
        self.refund_result_calls.append(
            {
                "reservation_id": reservation_id,
                "status": status,
                "amount_in_cents": amount_in_cents,
                "refund_id": refund_id,
                "source_ip": source_ip,
            }
        )
        if self.should_fail:
            raise RuntimeError("reservations unavailable")

    def notify_additional_charge_result(
        self, *, reservation_id, status, amount_in_cents, payment_id, source_ip=None
    ):
        self.additional_charge_result_calls.append(
            {
                "reservation_id": reservation_id,
                "status": status,
                "amount_in_cents": amount_in_cents,
                "payment_id": payment_id,
                "source_ip": source_ip,
            }
        )
        if self.should_fail:
            raise RuntimeError("reservations unavailable")


class FailingRefundGateway:
    def process_refund(self, *, reason: str) -> None:
        raise RuntimeError(f"refund gateway unavailable: {reason}")


# --- Payload builders ------------------------------------------------------


def build_charge_payload(token: str = "pm_tok_visa_ok") -> dict:
    return {
        "reservation_id": str(uuid4()),
        "traveler_id": str(uuid4()),
        "payment_method_token": token,
        "amount_in_cents": 125000,
        "currency": "cop",
        "idempotency_key": "booking-123-attempt-1",
    }


def build_checkout_payload() -> dict:
    return {
        "reservation_id": str(uuid4()),
        "traveler_id": str(uuid4()),
        "amount_in_cents": 287650,
        "currency": "cop",
        "property_name": "Renaissance Estate",
        "check_in_date": "2026-10-12",
        "check_out_date": "2026-10-17",
    }


# --- Engine + client fixtures ---------------------------------------------


@pytest.fixture(scope="function")
def test_engine():
    """Per-test SQLite engine, in-memory with StaticPool so a single
    connection is shared across threads (FastAPI TestClient).

    Each test gets a fresh schema; no manual cleanup is needed.
    """
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    try:
        yield engine
    finally:
        SQLModel.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture
def client(test_engine):
    """FastAPI TestClient bound to the per-test SQLite engine."""
    previous_skip_flag = os.environ.get("SKIP_DB_INIT_ON_STARTUP")
    os.environ["SKIP_DB_INIT_ON_STARTUP"] = "true"

    app = create_application()

    def override_get_session():
        with Session(test_engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()

    if previous_skip_flag is None:
        os.environ.pop("SKIP_DB_INIT_ON_STARTUP", None)
    else:
        os.environ["SKIP_DB_INIT_ON_STARTUP"] = previous_skip_flag
