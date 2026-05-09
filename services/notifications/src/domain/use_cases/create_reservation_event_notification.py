from datetime import datetime, timezone
from uuid import uuid4

from core.privacy import mask_email
from domain.ports.device_token_repository import DeviceTokenRepository
from domain.ports.notification_audit_repository import NotificationAuditRepository
from domain.ports.notification_preference_repository import (
    NotificationPreferenceRepository,
)
from domain.ports.notification_repository import NotificationRepository
from domain.ports.payment_event_source import PaymentEventSource
from domain.ports.push_sender import PushSender
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


_STATUS_CHANGE_EVENTS = {
    "booking_confirmed",
    "modification_confirmed",
    "cancellation_confirmed",
    "checkin_registered",
    "checkout_registered",
}
_ARRIVAL_EVENTS = {"arrival_reminder"}


class CreateReservationEventNotificationUseCase(
    BaseUseCase[ReservationEventNotificationRequest, NotificationResponse]
):
    def __init__(
        self,
        notification_repository: NotificationRepository,
        audit_repository: NotificationAuditRepository,
        traveler_profile_source: TravelerProfileSource,
        payment_event_source: PaymentEventSource,
        device_token_repository: DeviceTokenRepository | None = None,
        preference_repository: NotificationPreferenceRepository | None = None,
        push_sender: PushSender | None = None,
    ):
        self.notification_repository = notification_repository
        self.audit_repository = audit_repository
        self.traveler_profile_source = traveler_profile_source
        self.payment_event_source = payment_event_source
        self.device_token_repository = device_token_repository
        self.preference_repository = preference_repository
        self.push_sender = push_sender

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
        self._dispatch_push(stored, payload, now)
        return self._to_response(stored)

    def _dispatch_push(
        self,
        stored: NotificationRecord,
        payload: ReservationEventNotificationRequest,
        now: datetime,
    ) -> None:
        if (
            self.device_token_repository is None
            or self.preference_repository is None
            or self.push_sender is None
        ):
            return

        event_type = payload.event_type.value
        if not self._push_enabled_for_event(payload.traveler_id, event_type):
            self.audit_repository.add_log(
                NotificationAuditLogRecord(
                    notification_id=stored.notification_id,
                    traveler_id=stored.traveler_id,
                    entity_type="notification",
                    entity_id=str(stored.notification_id),
                    action=f"notification.reservation_event.{event_type}.push_skipped",
                    ip_address=payload.source_ip,
                    payload={"reason": "preference_disabled"},
                    created_at=now,
                    channel="push",
                    delivery_status="skipped_by_preference",
                )
            )
            return

        tokens = self.device_token_repository.list_active_for_user(payload.traveler_id)
        if not tokens:
            return

        title, body = self._push_copy(event_type, stored)
        deep_link = f"https://travelhub.app/reservations/{stored.reservation_id}"
        channel_id = (
            "arrival_reminder" if event_type in _ARRIVAL_EVENTS else "reservation_status"
        )
        for device in tokens:
            data = {
                "notification_id": str(stored.notification_id),
                "entity_type": "reservation",
                "entity_id": str(stored.reservation_id),
                "deep_link": deep_link,
                "channel_id": channel_id,
                "event_type": event_type,
            }
            result = self.push_sender.send(
                device_token=device.token, title=title, body=body, data=data
            )
            self.audit_repository.add_log(
                NotificationAuditLogRecord(
                    notification_id=stored.notification_id,
                    traveler_id=stored.traveler_id,
                    entity_type="reservation",
                    entity_id=str(stored.reservation_id),
                    action=f"notification.reservation_event.{event_type}.push_dispatched",
                    ip_address=payload.source_ip,
                    payload={
                        "platform": device.platform,
                        "error": result.error,
                        "title": title,
                        "body": body,
                        "deep_link": deep_link,
                    },
                    created_at=now,
                    channel="push",
                    provider_message_id=result.provider_message_id or None,
                    delivery_status="sent" if result.success else "failed",
                )
            )

    def _push_enabled_for_event(self, user_id, event_type: str) -> bool:
        prefs = self.preference_repository.get(user_id)
        if event_type in _STATUS_CHANGE_EVENTS:
            return prefs.status_changes_enabled
        if event_type in _ARRIVAL_EVENTS:
            return prefs.arrival_reminders_enabled
        return True

    def _push_copy(self, event_type: str, stored: NotificationRecord) -> tuple[str, str]:
        copy = {
            "booking_confirmed": (
                "Reserva confirmada",
                "Tu estancia ha sido confirmada satisfactoriamente. ¡Buen viaje!",
            ),
            "modification_confirmed": (
                "Reserva modificada",
                "Tu modificación de reserva fue confirmada.",
            ),
            "cancellation_confirmed": (
                "Reserva cancelada",
                "Tu cancelación fue procesada correctamente.",
            ),
            "checkin_registered": (
                "Check-in registrado",
                "Disfruta tu estancia. Tu check-in quedó registrado.",
            ),
            "checkout_registered": (
                "Check-out registrado",
                "Gracias por hospedarte con nosotros.",
            ),
            "arrival_reminder": (
                "Recordatorio de Check-in",
                "Tu check-in está cerca. Revisa tu itinerario y la ubicación del hotel.",
            ),
            "refund_initiated": (
                "Reembolso iniciado",
                "Tu reembolso fue iniciado y será procesado en breve.",
            ),
            "refund_succeeded": (
                "Reembolso completado",
                "Tu reembolso fue acreditado correctamente.",
            ),
            "refund_failed": (
                "Reembolso con problemas",
                "No pudimos completar tu reembolso. Pronto te contactaremos.",
            ),
        }
        return copy.get(event_type, ("TravelHub", stored.subject))

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
            "booking_confirmed": (
                "reservation_booking_confirmed_v1",
                f"Tu reserva {reservation_id} fue confirmada",
            ),
            "modification_confirmed": (
                "reservation_modification_confirmed_v1",
                f"Tu modificacion de reserva {reservation_id} fue confirmada",
            ),
            "cancellation_confirmed": (
                "reservation_cancellation_confirmed_v1",
                f"Tu cancelacion de reserva {reservation_id} fue confirmada",
            ),
            "checkin_registered": (
                "reservation_checkin_registered_v1",
                f"Check-in registrado para tu reserva {reservation_id}",
            ),
            "checkout_registered": (
                "reservation_checkout_registered_v1",
                f"Check-out registrado para tu reserva {reservation_id}",
            ),
            "arrival_reminder": (
                "reservation_arrival_reminder_v1",
                f"Recordatorio: tu check-in para la reserva {reservation_id} está cerca",
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
