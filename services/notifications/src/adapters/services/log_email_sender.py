import logging
from uuid import uuid4

from core.privacy import mask_email
from domain.ports.email_sender import EmailSender

logger = logging.getLogger(__name__)


class LogEmailSender(EmailSender):
    def send(self, *, recipient_email: str, subject: str, html_body: str) -> str:
        message_id = f"log-{uuid4()}"
        logger.info(
            "Notification email sent",
            extra={
                "message_id": message_id,
                "recipient_email": mask_email(recipient_email),
                "subject": subject,
                "body_length": len(html_body),
            },
        )
        return message_id
