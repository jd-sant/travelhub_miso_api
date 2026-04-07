import logging
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from core.config import settings
from domain.ports.otp_sender import OtpSender

logger = logging.getLogger(__name__)


class SmtpOtpSender(OtpSender):
    def send(self, email: str, code: str) -> None:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = "Tu codigo de verificacion - TravelHub"
        msg["From"] = settings.smtp_from
        msg["To"] = email

        html = (
            f"<h2>Codigo de verificacion</h2>"
            f"<p>Tu codigo OTP es: <strong>{code}</strong></p>"
            f"<p>Este codigo expira en {settings.otp_expiry_minutes} minutos.</p>"
            f"<p>Si no solicitaste este codigo, ignora este mensaje.</p>"
        )
        msg.attach(MIMEText(html, "html"))

        try:
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
                server.starttls(context=ssl.create_default_context())
                server.login(settings.smtp_user, settings.smtp_password)
                server.sendmail(settings.smtp_from, email, msg.as_string())
            logger.info("[OTP] Email sent to %s", email)
        except Exception:
            logger.exception("[OTP] Failed to send email to %s", email)
            raise
