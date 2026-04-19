import logging
from email.message import EmailMessage

import boto3

from core.config import settings
from domain.ports.email_sender import EmailSender

logger = logging.getLogger(__name__)


class SesEmailSender(EmailSender):
    """Envía correo HTML usando Amazon SES (SendRawEmail)."""

    def __init__(self, client=None, from_address: str | None = None) -> None:
        self._client = client or boto3.client("ses", region_name=settings.ses_region)
        self._from_address = from_address or settings.ses_from_address

    def send(self, *, recipient_email: str, subject: str, html_body: str) -> str:
        if not self._from_address:
            raise RuntimeError("SES_FROM_ADDRESS no esta configurado.")

        message = EmailMessage()
        message["From"] = self._from_address
        message["To"] = recipient_email
        message["Subject"] = subject
        message.set_content(html_body, subtype="html")

        response = self._client.send_raw_email(
            Source=self._from_address,
            Destinations=[recipient_email],
            RawMessage={"Data": message.as_bytes()},
        )
        message_id = response.get("MessageId", "")
        logger.info(
            "ses_email_sent",
            extra={"provider_message_id": message_id, "subject": subject},
        )
        return message_id
