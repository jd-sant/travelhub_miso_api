from datetime import datetime, timezone
from uuid import uuid4

from domain.ports.notification_audit_repository import NotificationAuditRepository
from domain.ports.notification_repository import NotificationRepository
from domain.ports.payment_confirmation_source import PaymentConfirmationSource
from domain.ports.traveler_profile_source import TravelerProfileSource
from core.privacy import mask_email
from domain.schemas.notification import (
    NotificationAuditLogRecord,
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
        audit_repository: NotificationAuditRepository,
        payment_confirmation_source: PaymentConfirmationSource,
        traveler_profile_source: TravelerProfileSource,
    ):
        self.notification_repository = notification_repository
        self.audit_repository = audit_repository
        self.payment_confirmation_source = payment_confirmation_source
        self.traveler_profile_source = traveler_profile_source

    def execute(self, payload: PaymentConfirmationRequest) -> NotificationResponse:
        existing = self.notification_repository.get_by_payment_id(payload.payment_id)
        if existing is not None:
            return self._to_response(existing)

        now = datetime.now(timezone.utc)
        confirmation = self.payment_confirmation_source.get_confirmation(payload.payment_id)
        self._assert_confirmed_payment(confirmation)
        traveler = self.traveler_profile_source.get_traveler(confirmation.traveler_id)

        subject = f"Confirmacion de pago de la reserva {confirmation.reservation_id}"
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
        return self._to_response(stored)

    def _assert_confirmed_payment(self, confirmation: PaymentConfirmationSourceRecord) -> None:
        if confirmation.status != "confirmed":
            raise InvalidPaymentConfirmationError(
                "Solo se pueden notificar pagos que ya esten confirmados."
            )
        if confirmation.receipt_number is None:
            raise InvalidPaymentConfirmationError(
                "El pago confirmado no tiene recibo disponible para notificacion."
            )

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
                "property_address": confirmation.property_address,
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
                "guests_count": confirmation.guests_count,
                "nights": confirmation.nights,
                "nightly_rate_in_cents": confirmation.nightly_rate_in_cents,
                "taxes_in_cents": confirmation.taxes_in_cents,
                "total_in_cents": confirmation.total_in_cents or confirmation.amount_in_cents,
                "cancellation_policy": confirmation.cancellation_policy,
            },
            "recipient": {
                "email_masked": mask_email(recipient_email),
            },
        }

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
