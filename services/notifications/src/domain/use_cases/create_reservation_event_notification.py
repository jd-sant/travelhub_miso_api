from datetime import datetime, timezone
from uuid import uuid4

from core.privacy import mask_email
from domain.ports.notification_audit_repository import NotificationAuditRepository
from domain.ports.notification_repository import NotificationRepository
from domain.ports.payment_event_source import PaymentEventSource
from domain.ports.traveler_profile_source import TravelerProfileSource
from domain.schemas.notification import (
    NotificationAuditLogRecord,
    NotificationRecord,
    NotificationResponse,
    NotificationStatus,
    ReservationEventNotificationRequest,
)
from domain.use_cases.base import BaseUseCase
from errors import PaymentConfirmationUnavailableError, TravelerProfileNotFoundError


class CreateReservationEventNotificationUseCase(
    BaseUseCase[ReservationEventNotificationRequest, NotificationResponse]
):
    def __init__(
        self,
        notification_repository: NotificationRepository,
        audit_repository: NotificationAuditRepository,
        traveler_profile_source: TravelerProfileSource,
        payment_event_source: PaymentEventSource,
    ):
        self.notification_repository = notification_repository
        self.audit_repository = audit_repository
        self.traveler_profile_source = traveler_profile_source
        self.payment_event_source = payment_event_source

    def execute(self, payload: ReservationEventNotificationRequest) -> NotificationResponse:
        now = datetime.now(timezone.utc)
        recipient_email, recipient_name = self._resolve_recipient(payload)

        payment_summary = None
        if payload.payment_id is not None:
            try:
                payment_summary = self.payment_event_source.get_payment(payload.payment_id)
            except PaymentConfirmationUnavailableError:
                payment_summary = None

        refund_summary = None
        if payload.refund_id is not None:
            try:
                refund_summary = self.payment_event_source.get_refund(payload.refund_id)
            except PaymentConfirmationUnavailableError:
                refund_summary = None

        template_code, subject = self._template_and_subject(payload.event_type.value, payload.reservation_id)
        notification = NotificationRecord(
            notification_id=uuid4(),
            traveler_id=payload.traveler_id,
            reservation_id=payload.reservation_id,
            payment_id=payload.payment_id,
            channel="email",
            template_code=template_code,
            status=NotificationStatus.pending,
            subject=subject,
            recipient_email=recipient_email,
            recipient_name=recipient_name,
            payload={
                "event": {
                    "type": payload.event_type.value,
                    "reservation_id": str(payload.reservation_id),
                },
                "payment": payment_summary.model_dump(mode="json") if payment_summary else None,
                "refund": refund_summary.model_dump(mode="json") if refund_summary else None,
                "recipient": {
                    "email_masked": mask_email(recipient_email),
                },
            },
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
                action=f"notification.reservation_event.{payload.event_type.value}.created",
                ip_address=payload.source_ip,
                payload=stored.payload,
                created_at=now,
            )
        )
        return self._to_response(stored)

    def _resolve_recipient(self, payload: ReservationEventNotificationRequest) -> tuple[str, str]:
        if payload.traveler_email and payload.traveler_name:
            return payload.traveler_email, payload.traveler_name

        try:
            traveler = self.traveler_profile_source.get_traveler(payload.traveler_id)
            return traveler.email, traveler.full_name
        except (TravelerProfileNotFoundError, PaymentConfirmationUnavailableError):
            fallback_email = f"traveler-{payload.traveler_id}@placeholder.local"
            return fallback_email, "Viajero"

    def _template_and_subject(self, event_type: str, reservation_id) -> tuple[str, str]:
        mapping = {
            "modification_confirmed": (
                "reservation_modification_confirmed_v1",
                f"Tu modificacion de reserva {reservation_id} fue confirmada",
            ),
            "cancellation_confirmed": (
                "reservation_cancellation_confirmed_v1",
                f"Tu cancelacion de reserva {reservation_id} fue confirmada",
            ),
            "refund_initiated": (
                "reservation_refund_initiated_v1",
                f"Tu reembolso de la reserva {reservation_id} fue iniciado",
            ),
            "refund_succeeded": (
                "reservation_refund_succeeded_v1",
                f"Tu reembolso de la reserva {reservation_id} fue completado",
            ),
            "refund_failed": (
                "reservation_refund_failed_v1",
                f"Tu reembolso de la reserva {reservation_id} fallo",
            ),
        }
        return mapping[event_type]

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
