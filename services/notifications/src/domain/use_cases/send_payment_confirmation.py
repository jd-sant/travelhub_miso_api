import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

from jinja2 import Environment, FileSystemLoader, select_autoescape

from core.privacy import mask_email
from domain.ports.delivery_attempt_repository import DeliveryAttemptRepository
from domain.ports.email_sender import EmailSender
from domain.ports.notification_audit_repository import NotificationAuditRepository
from domain.ports.notification_repository import NotificationRepository
from domain.schemas.notification import (
    DeliveryAttemptStatus,
    NotificationAuditLogRecord,
    NotificationDeliveryAttemptRecord,
    NotificationRecord,
    NotificationResponse,
    NotificationStatus,
)
from domain.use_cases.base import BaseUseCase
from errors import NotificationNotFoundError

logger = logging.getLogger(__name__)

_TEMPLATES_DIR = Path(__file__).resolve().parents[2] / "adapters" / "templates"
_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATES_DIR)),
    autoescape=select_autoescape(["html"]),
    trim_blocks=False,
    lstrip_blocks=False,
)

_RESERVATION_UPDATE_I18N = {
    "es": {
        "language_tag": "es",
        "title_cancelled": "Reserva cancelada por el hotel",
        "title_confirmed": "Reserva confirmada",
        "greeting": "Hola",
        "subtitle_cancelled": "Te compartimos el detalle de esta actualización sobre tu reserva.",
        "subtitle_confirmed": "Tu reserva fue actualizada correctamente.",
        "reservation_details": "Detalle de la reserva",
        "reservation_label": "Reserva",
        "status_label": "Estado",
        "status_cancelled": "cancelada",
        "status_confirmed": "confirmada",
        "reason_label": "Motivo",
        "description_label": "Descripción",
        "refund_title": "Proceso de reembolso",
        "refund_description": "El sistema inició automáticamente el reembolso según la política de cancelación vigente.",
        "refund_amount_label": "Monto estimado",
        "help_text": "Si necesitas ayuda adicional, revisa tu panel de reservas o contacta al hotel.",
        "footer": "Gracias por usar TravelHub.",
        "subject_cancelled": "Reserva cancelada",
        "subject_confirmed": "Reserva confirmada",
    },
    "en": {
        "language_tag": "en",
        "title_cancelled": "Reservation cancelled by the hotel",
        "title_confirmed": "Reservation confirmed",
        "greeting": "Hello",
        "subtitle_cancelled": "Here are the details of this reservation update.",
        "subtitle_confirmed": "Your reservation was updated successfully.",
        "reservation_details": "Reservation details",
        "reservation_label": "Reservation",
        "status_label": "Status",
        "status_cancelled": "cancelled",
        "status_confirmed": "confirmed",
        "reason_label": "Reason",
        "description_label": "Description",
        "refund_title": "Refund process",
        "refund_description": "The system automatically started the refund according to the active cancellation policy.",
        "refund_amount_label": "Estimated amount",
        "help_text": "If you need additional help, review your reservations panel or contact the hotel.",
        "footer": "Thanks for using TravelHub.",
        "subject_cancelled": "Reservation cancelled",
        "subject_confirmed": "Reservation confirmed",
    },
    "pt": {
        "language_tag": "pt",
        "title_cancelled": "Reserva cancelada pelo hotel",
        "title_confirmed": "Reserva confirmada",
        "greeting": "Olá",
        "subtitle_cancelled": "Compartilhamos os detalhes desta atualização da sua reserva.",
        "subtitle_confirmed": "Sua reserva foi atualizada com sucesso.",
        "reservation_details": "Detalhes da reserva",
        "reservation_label": "Reserva",
        "status_label": "Status",
        "status_cancelled": "cancelada",
        "status_confirmed": "confirmada",
        "reason_label": "Motivo",
        "description_label": "Descrição",
        "refund_title": "Processo de reembolso",
        "refund_description": "O sistema iniciou automaticamente o reembolso de acordo com a política de cancelamento vigente.",
        "refund_amount_label": "Valor estimado",
        "help_text": "Se precisar de ajuda adicional, consulte seu painel de reservas ou entre em contato com o hotel.",
        "footer": "Obrigado por usar a TravelHub.",
        "subject_cancelled": "Reserva cancelada",
        "subject_confirmed": "Reserva confirmada",
    },
}


class SendPaymentConfirmationUseCase(BaseUseCase[UUID, NotificationResponse]):
    def __init__(
        self,
        notification_repository: NotificationRepository,
        delivery_attempt_repository: DeliveryAttemptRepository,
        audit_repository: NotificationAuditRepository,
        email_sender: EmailSender,
    ):
        self.notification_repository = notification_repository
        self.delivery_attempt_repository = delivery_attempt_repository
        self.audit_repository = audit_repository
        self.email_sender = email_sender

    def execute(
        self,
        notification_id: UUID,
        source_ip: str | None = None,
        payment_confirmed_at: datetime | None = None,
    ) -> NotificationResponse:
        notification = self.notification_repository.get_by_id(notification_id)
        if notification is None:
            raise NotificationNotFoundError(f"Notification {notification_id} was not found")

        if notification.status == NotificationStatus.sent:
            return self._to_response(notification)

        html_body = self._render(notification)
        attempt_status = DeliveryAttemptStatus.sent
        failure_reason = None
        provider_message_id = None
        try:
            provider_message_id = self.email_sender.send(
                recipient_email=notification.recipient_email,
                subject=notification.subject,
                html_body=html_body,
            )
            notification.status = NotificationStatus.sent
        except Exception as exc:  # noqa: BLE001
            attempt_status = DeliveryAttemptStatus.failed
            failure_reason = str(exc)
            notification.status = NotificationStatus.failed

        email_sent_at = datetime.now(timezone.utc)
        notification.updated_at = email_sent_at
        stored_notification = self.notification_repository.update(notification)
        self.delivery_attempt_repository.add_attempt(
            NotificationDeliveryAttemptRecord(
                attempt_id=uuid4(),
                notification_id=stored_notification.notification_id,
                attempt_number=1,
                status=attempt_status,
                provider_message_id=provider_message_id,
                failure_reason=failure_reason,
                created_at=stored_notification.updated_at,
            )
        )

        audit_payload = {
            "provider_message_id": provider_message_id,
            "failure_reason": failure_reason,
            "status": stored_notification.status.value,
            "payment_confirmed_at": (
                payment_confirmed_at.isoformat() if payment_confirmed_at else None
            ),
            "notification_created_at": stored_notification.created_at.isoformat(),
            "email_sent_at": email_sent_at.isoformat(),
        }
        if payment_confirmed_at is not None:
            latency_ms = int(
                (email_sent_at - payment_confirmed_at).total_seconds() * 1000
            )
            audit_payload["latency_ms"] = latency_ms
            logger.info(
                "payment_confirmation_latency_ms",
                extra={
                    "notification_id": str(stored_notification.notification_id),
                    "latency_ms": latency_ms,
                    "sla_30s_met": latency_ms <= 30_000,
                    "status": stored_notification.status.value,
                },
            )

        self.audit_repository.add_log(
            NotificationAuditLogRecord(
                notification_id=stored_notification.notification_id,
                traveler_id=stored_notification.traveler_id,
                entity_type="notification",
                entity_id=str(stored_notification.notification_id),
                action=self._resolve_audit_action(stored_notification),
                ip_address=source_ip,
                payload=audit_payload,
                created_at=stored_notification.updated_at,
            )
        )
        return self._to_response(stored_notification)

    def _render(self, notification: NotificationRecord) -> str:
        if notification.template_code in {
            "reservation_confirmed_v1",
            "reservation_cancelled_v1",
        }:
            return self._render_reservation_update(notification)

        summary = notification.payload.get("payment_summary", {})
        currency = summary.get("currency", "")

        def _money(cents: int | None) -> str | None:
            if cents is None:
                return None
            return f"{cents / 100:.2f}"

        context = {
            "recipient_name": notification.recipient_name,
            "reservation_id": summary.get("reservation_id"),
            "receipt_number": summary.get("receipt_number"),
            "property_name": summary.get("property_name"),
            "property_address": summary.get("property_address"),
            "check_in_date": summary.get("check_in_date"),
            "check_out_date": summary.get("check_out_date"),
            "guests_count": summary.get("guests_count"),
            "nights": summary.get("nights"),
            "nightly_rate": _money(summary.get("nightly_rate_in_cents")),
            "taxes": _money(summary.get("taxes_in_cents")),
            "accommodation": _money(summary.get("accommodation_in_cents")),
            "cleaning_fee": _money(summary.get("cleaning_fee_in_cents")),
            "service_fee": _money(summary.get("service_fee_in_cents")),
            "total": _money(summary.get("total_in_cents") or summary.get("amount_in_cents")),
            "currency": currency,
            "cancellation_policy": (
                summary.get("cancellation_policy")
                or "Consulta la política de cancelación en tu panel de reservas."
            ),
        }
        return _env.get_template("payment_confirmation.html").render(**context)

    def _render_reservation_update(self, notification: NotificationRecord) -> str:
        summary = notification.payload.get("reservation_update", {})
        translations = self._reservation_update_translations(summary.get("locale"))
        refund_amount = summary.get("refund_amount_in_cents")
        is_cancelled = notification.template_code == "reservation_cancelled_v1"
        return _env.get_template("reservation_update.html").render(
            recipient_name=notification.recipient_name,
            reservation_id=summary.get("reservation_id"),
            status=(
                translations["status_cancelled"]
                if is_cancelled
                else translations["status_confirmed"]
            ),
            reason=summary.get("reason_code") or summary.get("reason"),
            description=summary.get("reason_note"),
            refund_requested=summary.get("refund_requested", False),
            refund_amount=(
                f"{refund_amount / 100:.2f}"
                if isinstance(refund_amount, int)
                else None
            ),
            translations=translations,
            language_tag=translations["language_tag"],
            is_cancelled=is_cancelled,
        )

    def _reservation_update_translations(self, locale: str | None) -> dict[str, str]:
        normalized = self._normalize_locale(locale)
        return _RESERVATION_UPDATE_I18N.get(
            normalized, _RESERVATION_UPDATE_I18N["es"]
        )

    def _normalize_locale(self, locale: str | None) -> str:
        if not locale:
            return "es"
        lowered = locale.strip().lower()
        if lowered.startswith("en"):
            return "en"
        if lowered.startswith("pt"):
            return "pt"
        return "es"

    def _html_to_text(self, html_body: str) -> str:
        text = re.sub(r"<br\\s*/?>", "\n", html_body, flags=re.IGNORECASE)
        text = re.sub(r"</(p|div|tr|h1|h2|h3|li|table|td)>", "\n", text, flags=re.IGNORECASE)
        text = re.sub(r"<[^>]+>", "", text)
        text = (
            text.replace("&nbsp;", " ")
            .replace("&amp;", "&")
            .replace("&lt;", "<")
            .replace("&gt;", ">")
        )
        lines = [line.strip() for line in text.splitlines()]
        return "\n".join(line for line in lines if line)

    def _resolve_audit_action(self, notification: NotificationRecord) -> str:
        prefix = {
            "payment_confirmation_v1": "notification.payment_confirmation",
            "reservation_confirmed_v1": "notification.reservation_confirmed",
            "reservation_cancelled_v1": "notification.reservation_cancelled",
        }.get(notification.template_code, "notification.delivery")
        suffix = (
            "sent"
            if notification.status == NotificationStatus.sent
            else "failed"
        )
        return f"{prefix}.{suffix}"

    def _to_response(self, notification: NotificationRecord) -> NotificationResponse:
        return NotificationResponse(
            notification_id=notification.notification_id,
            status=notification.status,
            recipient_email=mask_email(notification.recipient_email),
            subject=notification.subject,
            payment_id=notification.payment_id,
            reservation_id=notification.reservation_id,
            created_at=notification.created_at,
            updated_at=notification.updated_at,
        )
