from datetime import datetime, timezone
from uuid import uuid4, UUID

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
    ) -> NotificationResponse:
        notification = self.notification_repository.get_by_id(notification_id)
        if notification is None:
            raise NotificationNotFoundError(f"Notification {notification_id} was not found")

        if notification.status == NotificationStatus.sent:
            return self._to_response(notification)

        body = self._build_body(notification)
        attempt_status = DeliveryAttemptStatus.sent
        failure_reason = None
        provider_message_id = None
        try:
            provider_message_id = self.email_sender.send(
                recipient_email=notification.recipient_email,
                subject=notification.subject,
                body=body,
            )
            notification.status = NotificationStatus.sent
        except Exception as exc:  # noqa: BLE001
            attempt_status = DeliveryAttemptStatus.failed
            failure_reason = str(exc)
            notification.status = NotificationStatus.failed

        notification.updated_at = datetime.now(timezone.utc)
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
        self.audit_repository.add_log(
            NotificationAuditLogRecord(
                notification_id=stored_notification.notification_id,
                traveler_id=stored_notification.traveler_id,
                entity_type="notification",
                entity_id=str(stored_notification.notification_id),
                action=(
                    "notification.payment_confirmation.sent"
                    if stored_notification.status == NotificationStatus.sent
                    else "notification.payment_confirmation.failed"
                ),
                ip_address=source_ip,
                payload={
                    "provider_message_id": provider_message_id,
                    "failure_reason": failure_reason,
                    "status": stored_notification.status.value,
                },
                created_at=stored_notification.updated_at,
            )
        )
        return self._to_response(stored_notification)

    def _build_body(self, notification: NotificationRecord) -> str:
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
