import json
import logging
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
        if notification.template_code == "reservation_confirmed_v1":
            summary = notification.payload.get("reservation_update", {})
            return _env.get_template("reservation_update.html").render(
                recipient_name=notification.recipient_name,
                reservation_id=summary.get("reservation_id"),
                status="confirmada",
                reason=summary.get("reason"),
                refund_requested=False,
                refund_amount=None,
            )
        if notification.template_code == "reservation_cancelled_v1":
            summary = notification.payload.get("reservation_update", {})
            refund_amount = summary.get("refund_amount_in_cents")
            return _env.get_template("reservation_update.html").render(
                recipient_name=notification.recipient_name,
                reservation_id=summary.get("reservation_id"),
                status="cancelada",
                reason=summary.get("reason"),
                refund_requested=summary.get("refund_requested", False),
                refund_amount=(
                    f"{refund_amount / 100:.2f}"
                    if isinstance(refund_amount, int)
                    else None
                ),
            )

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
            "total": _money(summary.get("total_in_cents") or summary.get("amount_in_cents")),
            "currency": currency,
            "cancellation_policy": (
                summary.get("cancellation_policy")
                or "Consulta la política de cancelación en tu panel de reservas."
            ),
        }
        return _env.get_template("payment_confirmation.html").render(**context)
    
    def _build_body(self, notification: NotificationRecord) -> str:
        if notification.template_code == "payment_confirmation_v1":
            return self._build_payment_confirmation_body(notification)
        return self._build_reservation_event_body(notification)

    def _build_payment_confirmation_body(self, notification: NotificationRecord) -> str:
        payment_summary = notification.payload.get("payment_summary", {})
        lines = [
            f"Hola {notification.recipient_name},",
            "",
            "Tu pago fue confirmado exitosamente.",
            f"Reserva: {payment_summary.get('reservation_id')}",
            f"Pago: {payment_summary.get('payment_id')}",
            f"Monto: {payment_summary.get('amount_in_cents', 0) / 100:.2f} {payment_summary.get('currency', '')}",
        ]
        if payment_summary.get("property_name"):
            lines.append(f"Propiedad: {payment_summary['property_name']}")
        if payment_summary.get("check_in_date") and payment_summary.get("check_out_date"):
            lines.append(
                f"Fechas: {payment_summary['check_in_date']} - {payment_summary['check_out_date']}"
            )
        if payment_summary.get("receipt_number"):
            lines.append(f"Recibo: {payment_summary['receipt_number']}")
        return "\n".join(lines)

    def _build_reservation_event_body(self, notification: NotificationRecord) -> str:
        event = notification.payload.get("event", {})
        payment = notification.payload.get("payment") or {}
        refund = notification.payload.get("refund") or {}

        lines = [
            f"Hola {notification.recipient_name},",
            "",
            notification.subject,
            f"Reserva: {event.get('reservation_id')}",
        ]

        if payment:
            lines.append(f"Pago: {payment.get('payment_id')}")
            lines.append(
                f"Monto pago: {payment.get('amount_in_cents', 0) / 100:.2f} {payment.get('currency', '')}"
            )
            lines.append(f"Estado pago: {payment.get('status')}")

        if refund:
            lines.append(f"Reembolso: {refund.get('refund_id')}")
            lines.append(
                f"Monto reembolso: {refund.get('amount_in_cents', 0) / 100:.2f} {refund.get('currency', '')}"
            )
            lines.append(f"Estado reembolso: {refund.get('status')}")
            if refund.get("reason"):
                lines.append(f"Motivo: {refund.get('reason')}")

        return "\n".join(lines)

    def _audit_action(self, notification: NotificationRecord) -> str:
        base = notification.template_code.replace("_v1", "")
        suffix = "sent" if notification.status == NotificationStatus.sent else "failed"
        return f"notification.{base}.{suffix}"

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
