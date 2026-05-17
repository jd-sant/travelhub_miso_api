from datetime import datetime

from domain.ports.device_token_repository import DeviceTokenRepository
from domain.ports.notification_audit_repository import NotificationAuditRepository
from domain.ports.notification_preference_repository import (
    NotificationPreferenceRepository,
)
from domain.ports.push_sender import PushSender
from domain.schemas.notification import NotificationAuditLogRecord, NotificationRecord


_STATUS_CHANGE_EVENTS = {
    "booking_confirmed",
    "modification_confirmed",
    "cancellation_confirmed",
    "checkin_registered",
    "checkout_registered",
}
_ARRIVAL_EVENTS = {"arrival_reminder"}

_PUSH_COPY: dict[str, tuple[str, str]] = {
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
}


class PushNotifier:
    """Encapsula resolución de tokens, preferencias y envío FCM con auditoría."""

    def __init__(
        self,
        device_token_repository: DeviceTokenRepository,
        preference_repository: NotificationPreferenceRepository,
        push_sender: PushSender,
        audit_repository: NotificationAuditRepository,
    ):
        self.device_token_repository = device_token_repository
        self.preference_repository = preference_repository
        self.push_sender = push_sender
        self.audit_repository = audit_repository

    def dispatch(
        self,
        *,
        notification: NotificationRecord,
        event_type: str,
        source_ip: str | None,
        now: datetime,
    ) -> None:
        if not self._enabled_for(notification.traveler_id, event_type):
            self.audit_repository.add_log(
                NotificationAuditLogRecord(
                    notification_id=notification.notification_id,
                    traveler_id=notification.traveler_id,
                    entity_type="notification",
                    entity_id=str(notification.notification_id),
                    action=f"notification.{event_type}.push_skipped",
                    ip_address=source_ip,
                    payload={"reason": "preference_disabled"},
                    created_at=now,
                    channel="push",
                    delivery_status="skipped_by_preference",
                )
            )
            return

        tokens = self.device_token_repository.list_active_for_user(
            notification.traveler_id
        )
        if not tokens:
            return

        title, body = _PUSH_COPY.get(event_type, ("TravelHub", notification.subject))
        deep_link = f"https://travelhub.app/reservations/{notification.reservation_id}"
        channel_id = (
            "arrival_reminder" if event_type in _ARRIVAL_EVENTS else "reservation_status"
        )

        for device in tokens:
            data = {
                "notification_id": str(notification.notification_id),
                "entity_type": "reservation",
                "entity_id": str(notification.reservation_id),
                "deep_link": deep_link,
                "channel_id": channel_id,
                "event_type": event_type,
            }
            result = self.push_sender.send(
                device_token=device.token, title=title, body=body, data=data
            )
            self.audit_repository.add_log(
                NotificationAuditLogRecord(
                    notification_id=notification.notification_id,
                    traveler_id=notification.traveler_id,
                    entity_type="reservation",
                    entity_id=str(notification.reservation_id),
                    action=f"notification.{event_type}.push_dispatched",
                    ip_address=source_ip,
                    payload={
                        "platform": device.platform,
                        "error": result.error,
                        "title": title,
                        "message": body,
                        "deep_link": deep_link,
                    },
                    created_at=now,
                    channel="push",
                    provider_message_id=result.provider_message_id or None,
                    delivery_status="sent" if result.success else "failed",
                )
            )

    def _enabled_for(self, user_id, event_type: str) -> bool:
        prefs = self.preference_repository.get(user_id)
        if event_type in _STATUS_CHANGE_EVENTS:
            return prefs.status_changes_enabled
        if event_type in _ARRIVAL_EVENTS:
            return prefs.arrival_reminders_enabled
        return True
