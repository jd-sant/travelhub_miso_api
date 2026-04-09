import smtplib
from email.message import EmailMessage

from core.config import settings
from domain.ports.email_sender import EmailSender


class SmtpEmailSender(EmailSender):
    def send(self, *, recipient_email: str, subject: str, body: str) -> str:
        message = EmailMessage()
        message["From"] = settings.smtp_from
        message["To"] = recipient_email
        message["Subject"] = subject
        message.set_content(body)

        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as smtp:
            smtp.starttls()
            if settings.smtp_user:
                smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.send_message(message)
        return message["Message-ID"] or subject
