from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient

from adapters.services.payment_confirmation_client import HttpPaymentConfirmationClient
from assembly import get_create_payment_confirmation_use_case, get_notification_delivery_runner
from core.config import settings
from core.privacy import mask_email, sanitize_sensitive_data
from domain.schemas.notification import NotificationResponse, NotificationStatus
from entrypoints.api.main import create_application
from errors import (
    InvalidPaymentConfirmationError,
    PaymentConfirmationUnavailableError,
    TravelerProfileNotFoundError,
)


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict):
        self.status_code = status_code
        self._payload = payload
        self.request = httpx.Request("GET", "http://payments.local/confirmation")

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                "request failed",
                request=self.request,
                response=httpx.Response(self.status_code, request=self.request),
            )


class _SuccessUseCase:
    def execute(self, _payload):
        return NotificationResponse(
            notification_id=uuid4(),
            payment_id=uuid4(),
            reservation_id=uuid4(),
            subject="Payment confirmation",
            recipient_email="a***z@example.com",
            status=NotificationStatus.pending,
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
            updated_at=datetime(2026, 1, 1, tzinfo=UTC),
        )


class _Runner:
    def run_delivery(self, notification_id, source_ip=None):
        return None


@pytest.mark.parametrize(
    "exc, expected_status",
    [
        (InvalidPaymentConfirmationError("invalid"), 409),
        (TravelerProfileNotFoundError("traveler missing"), 404),
        (PaymentConfirmationUnavailableError("downstream"), 503),
    ],
)
def test_internal_router_maps_domain_errors_to_http(exc, expected_status):
    class _FailingUseCase:
        def execute(self, _payload):
            raise exc

    app = create_application()
    app.dependency_overrides[get_create_payment_confirmation_use_case] = lambda: _FailingUseCase()
    app.dependency_overrides[get_notification_delivery_runner] = lambda: _Runner()

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/internal/payment-confirmations",
            json={"payment_id": str(uuid4()), "source_ip": "127.0.0.1"},
            headers={"X-Internal-Api-Key": settings.internal_api_key},
        )

    assert response.status_code == expected_status


def test_internal_router_schedules_background_task_for_pending_notification():
    app = create_application()
    app.dependency_overrides[get_create_payment_confirmation_use_case] = lambda: _SuccessUseCase()
    app.dependency_overrides[get_notification_delivery_runner] = lambda: _Runner()

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/internal/payment-confirmations",
            json={"payment_id": str(uuid4()), "source_ip": "10.0.0.9"},
            headers={"X-Internal-Api-Key": settings.internal_api_key},
        )

    assert response.status_code == 201
    assert response.json()["status"] == "pending"


def test_payment_confirmation_client_success(monkeypatch):
    payment_id = uuid4()

    monkeypatch.setattr(
        httpx,
        "get",
        lambda *_args, **_kwargs: _FakeResponse(
            200,
            {
                "payment_id": str(payment_id),
                "reservation_id": str(uuid4()),
                "traveler_id": str(uuid4()),
                "status": "confirmed",
                "amount_in_cents": 120000,
                "currency": "COP",
                "receipt_id": str(uuid4()),
                "receipt_number": "RCPT-20260101-000001",
                "property_name": "Hotel Centro",
                "check_in_date": "2026-04-12",
                "check_out_date": "2026-04-15",
            },
        ),
    )

    record = HttpPaymentConfirmationClient().get_confirmation(payment_id)

    assert str(record.payment_id) == str(payment_id)
    assert record.status == "confirmed"
    assert record.amount_in_cents == 120000


def test_payment_confirmation_client_maps_404_and_transport_errors(monkeypatch):
    payment_id = uuid4()

    monkeypatch.setattr(
        httpx,
        "get",
        lambda *_args, **_kwargs: _FakeResponse(404, {}),
    )
    with pytest.raises(InvalidPaymentConfirmationError):
        HttpPaymentConfirmationClient().get_confirmation(payment_id)

    def _raise_transport(*_args, **_kwargs):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(httpx, "get", _raise_transport)
    with pytest.raises(PaymentConfirmationUnavailableError):
        HttpPaymentConfirmationClient().get_confirmation(payment_id)


def test_privacy_helpers_cover_sensitive_paths():
    payload = {
        "card_number": "4242 4242 4242 4242",
        "nested": {
            "free_text": "4111111111111111",
        },
        "list_data": ["ok", "5500000000000004"],
        "tuple_data": ("token", "hello"),
    }

    sanitized = sanitize_sensitive_data(payload)

    assert sanitized["card_number"] == "[REDACTED]"
    assert sanitized["nested"]["free_text"] == "[REDACTED]"
    assert sanitized["list_data"][1] == "[REDACTED]"
    assert mask_email("ab@example.com") == "**@example.com"
    assert mask_email("ana@example.com") == "a***a@example.com"
    assert mask_email("not-an-email") == "***"
