import smtplib
import ssl
from email.message import EmailMessage

from core.config import settings
from domain.ports.email_sender import EmailSender


class SmtpEmailSender(EmailSender):
    def send(self, *, recipient_email: str, subject: str, html_body: str) -> str:
        message = EmailMessage()
        message["From"] = settings.smtp_from
        message["To"] = recipient_email
        message["Subject"] = subject
        message.set_content("This email contains an HTML version of the reservation update.")
        message.add_alternative(html_body, subtype="html")

        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as smtp:
            smtp.starttls(context=ssl.create_default_context())
            if settings.smtp_user:
                smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.send_message(message)
        return message["Message-ID"] or subject
