import logging
from uuid import uuid4

from domain.ports.push_sender import PushSender, PushSendResult

logger = logging.getLogger(__name__)


class LogPushSender(PushSender):
    def send(
        self,
        *,
        device_token: str,
        title: str,
        body: str,
        data: dict[str, str],
    ) -> PushSendResult:
        message_id = f"log-push-{uuid4()}"
        masked_token = (device_token[:6] + "…" + device_token[-4:]) if len(device_token) > 12 else "***"
        logger.info(
            "push_notification_sent",
            extra={
                "provider_message_id": message_id,
                "device_token": masked_token,
                "title": title,
                "body_length": len(body),
                "data_keys": list(data.keys()),
            },
        )
        return PushSendResult(provider_message_id=message_id, success=True)
