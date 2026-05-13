"""Tests para la rama push del CreateReservationEventNotificationUseCase.

Verifica que el use case respeta preferencias del usuario, despacha a múltiples
device tokens y registra una fila de audit por device.
"""
from datetime import datetime, timezone
from uuid import UUID, uuid4

from domain.ports.device_token_repository import DeviceTokenRecord, DeviceTokenRepository
from domain.ports.notification_audit_repository import NotificationAuditRepository
from domain.ports.notification_preference_repository import (
    NotificationPreferenceRecord,
    NotificationPreferenceRepository,
)
from domain.ports.notification_repository import NotificationRepository
from domain.ports.payment_event_source import PaymentEventSource
from domain.ports.push_sender import PushSender, PushSendResult
from domain.ports.traveler_profile_source import TravelerProfileSource
from domain.schemas.notification import (
    NotificationRecord,
    ReservationEventNotificationRequest,
    ReservationNotificationType,
    TravelerProfileRecord,
)
from domain.use_cases.create_reservation_event_notification import (
    CreateReservationEventNotificationUseCase,
)


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class FakeNotificationRepository(NotificationRepository):
    def __init__(self):
        self.records: list[NotificationRecord] = []

    def create(self, notification: NotificationRecord) -> NotificationRecord:
        self.records.append(notification)
        return notification

    def update(self, notification: NotificationRecord) -> NotificationRecord:  # pragma: no cover
        return notification

    def get_by_id(self, notification_id):  # pragma: no cover
        return next((r for r in self.records if r.notification_id == notification_id), None)

    def get_by_payment_id(self, payment_id):  # pragma: no cover
        return None

    def get_by_reservation_and_template(self, **kwargs):  # pragma: no cover
        return None


class FakeAuditRepository(NotificationAuditRepository):
    def __init__(self):
        self.logs = []

    def add_log(self, record):
        self.logs.append(record)


class FakeTravelerProfileSource(TravelerProfileSource):
    def get_traveler(self, traveler_id):
        return TravelerProfileRecord(
            traveler_id=traveler_id,
            email="t@example.com",
            full_name="Test Traveler",
        )


class FakePaymentEventSource(PaymentEventSource):
    def get_payment(self, payment_id):  # pragma: no cover
        raise NotImplementedError

    def get_refund(self, refund_id):  # pragma: no cover
        raise NotImplementedError


class FakeDeviceTokenRepository(DeviceTokenRepository):
    def __init__(self, tokens: list[DeviceTokenRecord] | None = None):
        self._tokens = tokens or []

    def upsert(self, **kwargs):  # pragma: no cover
        raise NotImplementedError

    def revoke(self, **kwargs):  # pragma: no cover
        raise NotImplementedError

    def list_active_for_user(self, user_id: UUID):
        return [t for t in self._tokens if t.user_id == user_id and t.revoked_at is None]


class FakePreferenceRepository(NotificationPreferenceRepository):
    def __init__(self, status_changes=True, arrival_reminders=True):
        self._status_changes = status_changes
        self._arrival_reminders = arrival_reminders

    def get(self, user_id):
        return NotificationPreferenceRecord(
            user_id=user_id,
            status_changes_enabled=self._status_changes,
            arrival_reminders_enabled=self._arrival_reminders,
        )

    def upsert(self, **kwargs):  # pragma: no cover
        raise NotImplementedError


class RecordingPushSender(PushSender):
    def __init__(self, success=True, provider_id="msg-id"):
        self.calls = []
        self._success = success
        self._provider_id = provider_id

    def send(self, *, device_token, title, body, data):
        self.calls.append({"token": device_token, "title": title, "body": body, "data": data})
        return PushSendResult(
            provider_message_id=self._provider_id if self._success else "",
            success=self._success,
            error=None if self._success else "fcm_error",
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _device(user_id: UUID, token: str) -> DeviceTokenRecord:
    return DeviceTokenRecord(
        user_id=user_id,
        token=token,
        platform="android",
        app_version="1.0.0",
        last_seen_at=datetime.now(timezone.utc),
        revoked_at=None,
    )


def _build_use_case(
    *,
    devices: list[DeviceTokenRecord] | None = None,
    status_changes=True,
    arrival_reminders=True,
    sender_success=True,
    use_push_ports=True,
):
    notif = FakeNotificationRepository()
    audit = FakeAuditRepository()
    sender = RecordingPushSender(success=sender_success)
    if use_push_ports:
        uc = CreateReservationEventNotificationUseCase(
            notif,
            audit,
            FakeTravelerProfileSource(),
            FakePaymentEventSource(),
            device_token_repository=FakeDeviceTokenRepository(devices or []),
            preference_repository=FakePreferenceRepository(
                status_changes=status_changes,
                arrival_reminders=arrival_reminders,
            ),
            push_sender=sender,
        )
    else:
        uc = CreateReservationEventNotificationUseCase(
            notif, audit, FakeTravelerProfileSource(), FakePaymentEventSource()
        )
    return uc, notif, audit, sender


def _request(traveler_id: UUID, event: ReservationNotificationType):
    return ReservationEventNotificationRequest(
        reservation_id=uuid4(),
        traveler_id=traveler_id,
        event_type=event,
        source_ip="127.0.0.1",
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_dispatches_push_to_all_active_devices_for_status_change():
    traveler = uuid4()
    devices = [_device(traveler, "tok-1"), _device(traveler, "tok-2")]
    uc, notif, audit, sender = _build_use_case(devices=devices)

    uc.execute(_request(traveler, ReservationNotificationType.booking_confirmed))

    assert len(sender.calls) == 2
    assert {c["token"] for c in sender.calls} == {"tok-1", "tok-2"}
    assert sender.calls[0]["title"] == "Reserva confirmada"
    push_audits = [a for a in audit.logs if a.channel == "push"]
    assert len(push_audits) == 2
    assert all(a.delivery_status == "sent" for a in push_audits)
    assert all(a.provider_message_id == "msg-id" for a in push_audits)
    assert all(a.entity_type == "reservation" for a in push_audits)


def test_skips_push_when_status_changes_preference_disabled():
    traveler = uuid4()
    devices = [_device(traveler, "tok-1")]
    uc, _, audit, sender = _build_use_case(devices=devices, status_changes=False)

    uc.execute(_request(traveler, ReservationNotificationType.modification_confirmed))

    assert sender.calls == []
    skipped = [a for a in audit.logs if a.channel == "push"]
    assert len(skipped) == 1
    assert skipped[0].delivery_status == "skipped_by_preference"


def test_skips_push_when_arrival_reminder_preference_disabled():
    traveler = uuid4()
    devices = [_device(traveler, "tok-1")]
    uc, _, audit, sender = _build_use_case(devices=devices, arrival_reminders=False)

    uc.execute(_request(traveler, ReservationNotificationType.arrival_reminder))

    assert sender.calls == []
    skipped = [a for a in audit.logs if a.channel == "push"]
    assert len(skipped) == 1
    assert skipped[0].delivery_status == "skipped_by_preference"


def test_arrival_reminder_uses_arrival_channel_id():
    traveler = uuid4()
    devices = [_device(traveler, "tok-1")]
    uc, _, _, sender = _build_use_case(devices=devices)

    uc.execute(_request(traveler, ReservationNotificationType.arrival_reminder))

    assert sender.calls[0]["data"]["channel_id"] == "arrival_reminder"
    assert sender.calls[0]["data"]["event_type"] == "arrival_reminder"


def test_status_change_uses_reservation_status_channel_id():
    traveler = uuid4()
    devices = [_device(traveler, "tok-1")]
    uc, _, _, sender = _build_use_case(devices=devices)

    uc.execute(_request(traveler, ReservationNotificationType.checkin_registered))

    assert sender.calls[0]["data"]["channel_id"] == "reservation_status"
    assert sender.calls[0]["title"] == "Check-in registrado"


def test_failed_send_records_audit_with_failed_status():
    traveler = uuid4()
    devices = [_device(traveler, "tok-1")]
    uc, _, audit, sender = _build_use_case(devices=devices, sender_success=False)

    uc.execute(_request(traveler, ReservationNotificationType.booking_confirmed))

    push_audits = [a for a in audit.logs if a.channel == "push"]
    assert len(push_audits) == 1
    assert push_audits[0].delivery_status == "failed"
    assert push_audits[0].provider_message_id is None


def test_no_push_when_device_repository_is_none():
    traveler = uuid4()
    uc, _, audit, sender = _build_use_case(use_push_ports=False)

    uc.execute(_request(traveler, ReservationNotificationType.booking_confirmed))

    assert sender.calls == []
    assert all(a.channel == "email" for a in audit.logs)


def test_no_push_when_user_has_no_active_devices():
    traveler = uuid4()
    uc, _, audit, sender = _build_use_case(devices=[])

    uc.execute(_request(traveler, ReservationNotificationType.booking_confirmed))

    assert sender.calls == []
    push_audits = [a for a in audit.logs if a.channel == "push"]
    assert push_audits == []


def test_revoked_devices_are_filtered_out():
    traveler = uuid4()
    revoked = DeviceTokenRecord(
        user_id=traveler,
        token="old",
        platform="android",
        app_version="0.9",
        last_seen_at=datetime.now(timezone.utc),
        revoked_at=datetime.now(timezone.utc),
    )
    active = _device(traveler, "active")
    uc, _, _, sender = _build_use_case(devices=[revoked, active])

    uc.execute(_request(traveler, ReservationNotificationType.booking_confirmed))

    assert len(sender.calls) == 1
    assert sender.calls[0]["token"] == "active"


def test_deep_link_targets_reservation_detail():
    traveler = uuid4()
    devices = [_device(traveler, "tok-1")]
    uc, _, _, sender = _build_use_case(devices=devices)

    request = _request(traveler, ReservationNotificationType.booking_confirmed)
    uc.execute(request)

    assert sender.calls[0]["data"]["deep_link"] == (
        f"https://travelhub.app/reservations/{request.reservation_id}"
    )
    assert sender.calls[0]["data"]["entity_type"] == "reservation"
    assert sender.calls[0]["data"]["entity_id"] == str(request.reservation_id)
