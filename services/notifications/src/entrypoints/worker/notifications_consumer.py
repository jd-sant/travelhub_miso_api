"""Entrypoint del worker: consume Notificaciones Queue (SQS) y envía correos."""

from __future__ import annotations

import logging

from adapters.services.sqs_notification_consumer import SqsNotificationConsumer
from core.config import settings


def _build_email_sender():
    if settings.ses_from_address:
        from adapters.services.ses_email_sender import SesEmailSender

        return SesEmailSender()
    if settings.smtp_host:
        from adapters.services.smtp_email_sender import SmtpEmailSender

        return SmtpEmailSender()
    from adapters.services.log_email_sender import LogEmailSender

    return LogEmailSender()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    consumer = SqsNotificationConsumer(email_sender=_build_email_sender())
    consumer.run_forever()


if __name__ == "__main__":
    main()
