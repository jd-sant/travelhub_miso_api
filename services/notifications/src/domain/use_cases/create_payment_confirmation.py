from datetime import datetime, timezone
from uuid import uuid4

from domain.ports.delivery_attempt_repository import DeliveryAttemptRepository
from domain.ports.email_sender import EmailSender
from domain.ports.notification_audit_repository import NotificationAuditRepository
from domain.ports.notification_repository import NotificationRepository
from domain.ports.payment_confirmation_source import PaymentConfirmationSource
from domain.ports.traveler_profile_source import TravelerProfileSource
from core.privacy import mask_email
from domain.schemas.notification import (
    DeliveryAttemptStatus,
    NotificationAuditLogRecord,
    NotificationDeliveryAttemptRecord,
    NotificationRecord,
    PaymentConfirmationSourceRecord,
    NotificationResponse,
    NotificationStatus,
    PaymentConfirmationRequest,
)
from domain.use_cases.base import BaseUseCase
from errors import InvalidPaymentConfirmationError


class CreatePaymentConfirmationUseCase(
    BaseUseCase[PaymentConfirmationRequest, NotificationResponse]
):
    def __init__(
        self,
        notification_repository: NotificationRepository,
        delivery_attempt_repository: DeliveryAttemptRepository,
        audit_repository: NotificationAuditRepository,
        payment_confirmation_source: PaymentConfirmationSource,
        traveler_profile_source: TravelerProfileSource,
        email_sender: EmailSender,
    ):
        self.notification_repository = notification_repository
        self.delivery_attempt_repository = delivery_attempt_repository
        self.audit_repository = audit_repository
        self.payment_confirmation_source = payment_confirmation_source
        self.traveler_profile_source = traveler_profile_source
        self.email_sender = email_sender

    def execute(self, payload: PaymentConfirmationRequest) -> NotificationResponse:
        existing = self.notification_repository.get_by_payment_id(payload.payment_id)
        if existing is not None:
            return self._to_response(existing)

        now = datetime.now(timezone.utc)
        confirmation = self.payment_confirmation_source.get_confirmation(payload.payment_id)
        self._assert_confirmed_payment(confirmation)
        traveler = self.traveler_profile_source.get_traveler(confirmation.traveler_id)

        subject = f"Confirmacion de pago de la reserva {confirmation.reservation_id}"
        body = self._build_body(confirmation, traveler.full_name)
        notification = NotificationRecord(
            notification_id=uuid4(),
            traveler_id=confirmation.traveler_id,
            reservation_id=confirmation.reservation_id,
            payment_id=confirmation.payment_id,
            channel="email",
            template_code="payment_confirmation_v1",
            status=NotificationStatus.pending,
            subject=subject,
            recipient_email=traveler.email,
            recipient_name=traveler.full_name,
            payload=self._build_notification_payload(confirmation, traveler.email),
            created_at=now,
            updated_at=now,
        )
        stored = self.notification_repository.create(notification)
        self.audit_repository.add_log(
            NotificationAuditLogRecord(
                notification_id=stored.notification_id,
                traveler_id=stored.traveler_id,
                entity_type="notification",
                entity_id=str(stored.notification_id),
                action="notification.payment_confirmation.created",
                ip_address=payload.source_ip,
                payload=stored.payload,
                created_at=now,
            )
        )

        attempt_status = DeliveryAttemptStatus.sent
        failure_reason = None
        provider_message_id = None
        try:
            provider_message_id = self.email_sender.send(
                recipient_email=stored.recipient_email,
                subject=stored.subject,
                body=body,
            )
            stored.status = NotificationStatus.sent
        except Exception as exc:  # noqa: BLE001
            attempt_status = DeliveryAttemptStatus.failed
            failure_reason = str(exc)
            stored.status = NotificationStatus.failed

        stored.updated_at = datetime.now(timezone.utc)
        stored = self.notification_repository.update(stored)
        self.delivery_attempt_repository.add_attempt(
            NotificationDeliveryAttemptRecord(
                attempt_id=uuid4(),
                notification_id=stored.notification_id,
                attempt_number=1,
                status=attempt_status,
                provider_message_id=provider_message_id,
                failure_reason=failure_reason,
                created_at=stored.updated_at,
            )
        )
        self.audit_repository.add_log(
            NotificationAuditLogRecord(
                notification_id=stored.notification_id,
                traveler_id=stored.traveler_id,
                entity_type="notification",
                entity_id=str(stored.notification_id),
                action=(
                    "notification.payment_confirmation.sent"
                    if stored.status == NotificationStatus.sent
                    else "notification.payment_confirmation.failed"
                ),
                ip_address=payload.source_ip,
                payload={
                    "provider_message_id": provider_message_id,
                    "failure_reason": failure_reason,
                    "status": stored.status.value,
                },
                created_at=stored.updated_at,
            )
        )
        return NotificationResponse(
            notification_id=stored.notification_id,
            status=stored.status,
            recipient_email=stored.recipient_email,
            subject=stored.subject,
            payment_id=stored.payment_id,
            reservation_id=stored.reservation_id,
            created_at=stored.created_at,
            updated_at=stored.updated_at,
        )

    def _assert_confirmed_payment(self, confirmation: PaymentConfirmationSourceRecord) -> None:
        if confirmation.status != "confirmed":
            raise InvalidPaymentConfirmationError(
                "Solo se pueden notificar pagos que ya esten confirmados."
            )
        if confirmation.receipt_number is None:
            raise InvalidPaymentConfirmationError(
                "El pago confirmado no tiene recibo disponible para notificacion."
            )

    def _build_body(self, payload: PaymentConfirmationSourceRecord, recipient_name: str) -> str:
        lines = [
            f"Hola {recipient_name},",
            "",
            "Tu pago fue confirmado exitosamente.",
            f"Reserva: {payload.reservation_id}",
            f"Pago: {payload.payment_id}",
            f"Monto: {payload.amount_in_cents / 100:.2f} {payload.currency}",
        ]
        if payload.property_name:
            lines.append(f"Propiedad: {payload.property_name}")
        if payload.check_in_date and payload.check_out_date:
            lines.append(
                f"Fechas: {payload.check_in_date.isoformat()} - {payload.check_out_date.isoformat()}"
            )
        if payload.receipt_number:
            lines.append(f"Recibo: {payload.receipt_number}")
        return "\n".join(lines)

    def _build_notification_payload(
        self,
        confirmation: PaymentConfirmationSourceRecord,
        recipient_email: str,
    ) -> dict:
        return {
            "payment_summary": {
                "payment_id": str(confirmation.payment_id),
                "reservation_id": str(confirmation.reservation_id),
                "traveler_id": str(confirmation.traveler_id),
                "status": confirmation.status,
                "amount_in_cents": confirmation.amount_in_cents,
                "currency": confirmation.currency,
                "receipt_id": str(confirmation.receipt_id) if confirmation.receipt_id else None,
                "receipt_number": confirmation.receipt_number,
                "property_name": confirmation.property_name,
                "check_in_date": (
                    confirmation.check_in_date.isoformat()
                    if confirmation.check_in_date
                    else None
                ),
                "check_out_date": (
                    confirmation.check_out_date.isoformat()
                    if confirmation.check_out_date
                    else None
                ),
            },
            "recipient": {
                "email_masked": mask_email(recipient_email),
            },
        }

    def _to_response(self, notification: NotificationRecord) -> NotificationResponse:
        return NotificationResponse(
            notification_id=notification.notification_id,
            status=notification.status,
            recipient_email=notification.recipient_email,
            subject=notification.subject,
            payment_id=notification.payment_id,
            reservation_id=notification.reservation_id,
            created_at=notification.created_at,
            updated_at=notification.updated_at,
        )
