import logging
from uuid import uuid4

from domain.ports.email_sender import EmailSender

logger = logging.getLogger(__name__)


class LogEmailSender(EmailSender):
    def send(self, *, recipient_email: str, subject: str, body: str) -> str:
        message_id = f"log-{uuid4()}"
        logger.info(
            "Notification email sent",
            extra={
                "message_id": message_id,
                "recipient_email": recipient_email,
                "subject": subject,
                "body": body,
            },
        )
        return message_id
