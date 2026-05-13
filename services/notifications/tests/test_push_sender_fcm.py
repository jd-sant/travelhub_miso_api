"""Tests para FcmPushSender.

Mockea las credenciales de Google y httpx para verificar que el adapter
construye el payload correcto y mapea respuestas HTTP a PushSendResult.
"""
import httpx
import pytest

from adapters.services import fcm_push_sender as fcm_module
from adapters.services.fcm_push_sender import FcmPushSender


class _StubCredentials:
    """Sustituto de google.oauth2.service_account.Credentials para no requerir
    una llave RSA real en tests."""

    def __init__(self):
        self.valid = True
        self.token = "stub-access-token"

    def refresh(self, request):  # pragma: no cover - no debería invocarse
        self.valid = True


@pytest.fixture
def patched_credentials(monkeypatch):
    monkeypatch.setattr(
        fcm_module.service_account.Credentials,
        "from_service_account_info",
        lambda info, scopes: _StubCredentials(),
    )


def _build_sender(transport: httpx.MockTransport) -> FcmPushSender:
    return FcmPushSender(
        project_id="travelhub-test",
        service_account_info={"type": "service_account", "project_id": "travelhub-test"},
        http_client=httpx.Client(transport=transport),
    )


def test_send_success_parses_provider_message_id(patched_credentials):
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["headers"] = dict(request.headers)
        captured["json"] = request.read()
        return httpx.Response(
            200,
            json={"name": "projects/travelhub-test/messages/0:abc123"},
        )

    sender = _build_sender(httpx.MockTransport(handler))
    result = sender.send(
        device_token="token-xyz",
        title="Reserva confirmada",
        body="Tu reserva ha sido confirmada",
        data={
            "deep_link": "https://travelhub.app/reservations/123",
            "channel_id": "reservation_status",
            "entity_id": "123",
        },
    )

    assert result.success is True
    assert result.provider_message_id == "0:abc123"
    assert result.error is None
    assert captured["url"].endswith("/v1/projects/travelhub-test/messages:send")
    assert captured["headers"].get("authorization") == "Bearer stub-access-token"


def test_send_payload_includes_android_channel_and_click_action(patched_credentials):
    import json

    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.read())
        return httpx.Response(200, json={"name": "projects/x/messages/m"})

    sender = _build_sender(httpx.MockTransport(handler))
    sender.send(
        device_token="t",
        title="Recordatorio",
        body="Tu check-in está cerca",
        data={
            "deep_link": "travelhub://reservation/abc",
            "channel_id": "arrival_reminder",
        },
    )

    msg = captured["body"]["message"]
    assert msg["token"] == "t"
    assert msg["notification"] == {"title": "Recordatorio", "body": "Tu check-in está cerca"}
    assert msg["data"]["channel_id"] == "arrival_reminder"
    assert msg["data"]["deep_link"] == "travelhub://reservation/abc"
    assert msg["android"]["priority"] == "HIGH"
    assert msg["android"]["notification"]["channel_id"] == "arrival_reminder"
    assert msg["android"]["notification"]["click_action"] == "travelhub://reservation/abc"


def test_send_http_4xx_returns_failure_result(patched_credentials):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"error": {"message": "invalid token"}})

    sender = _build_sender(httpx.MockTransport(handler))
    result = sender.send(
        device_token="bad",
        title="x",
        body="y",
        data={},
    )

    assert result.success is False
    assert result.provider_message_id == ""
    assert result.error == "http_400"


def test_send_transport_error_returns_failure_result(patched_credentials):
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route")

    sender = _build_sender(httpx.MockTransport(handler))
    result = sender.send(device_token="t", title="x", body="y", data={})

    assert result.success is False
    assert result.error == "no route"


def test_constructor_requires_project_id(monkeypatch, patched_credentials):
    monkeypatch.delenv("FCM_PROJECT_ID", raising=False)
    with pytest.raises(RuntimeError, match="FCM_PROJECT_ID"):
        FcmPushSender(service_account_info={"type": "service_account"})
