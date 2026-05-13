import json
import logging
from typing import Any

import httpx
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2 import service_account

from core.config import settings
from domain.ports.push_sender import PushSender, PushSendResult

logger = logging.getLogger(__name__)

_FCM_SCOPE = "https://www.googleapis.com/auth/firebase.messaging"
_FCM_ENDPOINT = "https://fcm.googleapis.com/v1/projects/{project_id}/messages:send"


class FcmPushSender(PushSender):
    """Envía push a Android usando FCM HTTP v1 API.

    Requiere una service account JSON cuyo contenido se pasa en
    `FCM_SERVICE_ACCOUNT_JSON` (string con el JSON completo) y el
    `FCM_PROJECT_ID` del proyecto Firebase.
    """

    def __init__(
        self,
        project_id: str | None = None,
        service_account_info: dict[str, Any] | None = None,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._project_id = project_id or settings.fcm_project_id
        if not self._project_id:
            raise RuntimeError("FCM_PROJECT_ID no está configurado.")

        info = service_account_info or self._load_service_account_info()
        self._credentials = service_account.Credentials.from_service_account_info(
            info, scopes=[_FCM_SCOPE]
        )
        self._http = http_client or httpx.Client(timeout=10.0)

    @staticmethod
    def _load_service_account_info() -> dict[str, Any]:
        raw = settings.fcm_service_account_json
        if not raw:
            raise RuntimeError("FCM_SERVICE_ACCOUNT_JSON no está configurado.")
        return json.loads(raw)

    def _access_token(self) -> str:
        if not self._credentials.valid:
            self._credentials.refresh(GoogleAuthRequest())
        return self._credentials.token

    def send(
        self,
        *,
        device_token: str,
        title: str,
        body: str,
        data: dict[str, str],
    ) -> PushSendResult:
        url = _FCM_ENDPOINT.format(project_id=self._project_id)
        payload = {
            "message": {
                "token": device_token,
                "notification": {"title": title, "body": body},
                "data": {k: str(v) for k, v in data.items()},
                "android": {
                    "priority": "HIGH",
                    "notification": {
                        "channel_id": data.get("channel_id", "reservation_status"),
                        "click_action": data.get("deep_link", ""),
                    },
                },
            }
        }
        headers = {
            "Authorization": f"Bearer {self._access_token()}",
            "Content-Type": "application/json; charset=UTF-8",
        }
        try:
            response = self._http.post(url, headers=headers, json=payload)
        except httpx.HTTPError as exc:
            logger.warning("fcm_push_transport_error", extra={"error": str(exc)})
            return PushSendResult(provider_message_id="", success=False, error=str(exc))

        if response.status_code >= 400:
            logger.warning(
                "fcm_push_failed",
                extra={"status": response.status_code, "body": response.text[:500]},
            )
            return PushSendResult(
                provider_message_id="",
                success=False,
                error=f"http_{response.status_code}",
            )

        data_resp = response.json()
        message_name = data_resp.get("name", "")
        message_id = message_name.split("/")[-1] if message_name else ""
        return PushSendResult(provider_message_id=message_id, success=True)
