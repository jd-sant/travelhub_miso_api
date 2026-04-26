from datetime import datetime, timezone
from uuid import uuid4

from domain.ports.notification_audit_repository import NotificationAuditRepository
from domain.ports.notification_repository import NotificationRepository
from domain.ports.traveler_profile_source import TravelerProfileSource
from core.privacy import mask_email
from domain.schemas.notification import (
    NotificationAuditLogRecord,
    NotificationRecord,
    NotificationResponse,
    NotificationStatus,
    ReservationUpdateRequest,
)
from domain.use_cases.base import BaseUseCase


class CreateReservationUpdateUseCase(
    BaseUseCase[ReservationUpdateRequest, NotificationResponse]
):
    def __init__(
        self,
        notification_repository: NotificationRepository,
        audit_repository: NotificationAuditRepository,
        traveler_profile_source: TravelerProfileSource,
    ):
        self.notification_repository = notification_repository
        self.audit_repository = audit_repository
        self.traveler_profile_source = traveler_profile_source

    def execute(self, payload: ReservationUpdateRequest) -> NotificationResponse:
        template_code = (
            "reservation_cancelled_v1"
            if payload.status == "cancelled"
            else "reservation_confirmed_v1"
        )
        existing = self.notification_repository.get_by_reservation_and_template(
            reservation_id=payload.reservation_id,
            template_code=template_code,
        )
        if existing is not None:
            return self._to_response(existing)

        traveler = self.traveler_profile_source.get_traveler(payload.traveler_id)
        now = datetime.now(timezone.utc)
        subject = (
            f"Reserva cancelada {payload.reservation_id}"
            if payload.status == "cancelled"
            else f"Reserva confirmada {payload.reservation_id}"
        )
        notification = NotificationRecord(
            notification_id=uuid4(),
            traveler_id=payload.traveler_id,
            reservation_id=payload.reservation_id,
            payment_id=None,
            channel="email",
            template_code=template_code,
            status=NotificationStatus.pending,
            subject=subject,
            recipient_email=traveler.email,
            recipient_name=traveler.full_name,
            payload={
                "reservation_update": {
                    "reservation_id": str(payload.reservation_id),
                    "status": payload.status,
                    "reason": payload.reason,
                    "reason_code": payload.reason_code,
                    "reason_note": payload.reason_note,
                    "refund_requested": payload.refund_requested,
                    "refund_amount_in_cents": payload.refund_amount_in_cents,
                },
                "recipient": {
                    "email_masked": mask_email(traveler.email),
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
                action=(
                    "notification.reservation_cancelled.created"
                    if payload.status == "cancelled"
                    else "notification.reservation_confirmed.created"
                ),
                ip_address=payload.source_ip,
                payload=stored.payload,
                created_at=stored.created_at,
            )
        )
        return self._to_response(stored)

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
