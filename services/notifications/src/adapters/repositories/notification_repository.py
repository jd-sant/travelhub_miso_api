from uuid import UUID

from sqlmodel import Session, select

from adapters.models.notification import Notification
from domain.ports.notification_repository import NotificationRepository
from domain.schemas.notification import NotificationRecord, NotificationStatus


def _to_record(model: Notification) -> NotificationRecord:
    return NotificationRecord(
        notification_id=model.id,
        traveler_id=model.traveler_id,
        reservation_id=model.reservation_id,
        payment_id=model.payment_id,
        channel=model.channel,
        template_code=model.template_code,
        status=NotificationStatus(model.status),
        subject=model.subject,
        recipient_email=model.recipient_email,
        recipient_name=model.recipient_name,
        payload=model.payload,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


class SQLModelNotificationRepository(NotificationRepository):
    def __init__(self, session: Session):
        self.session = session

    def create(self, notification: NotificationRecord) -> NotificationRecord:
        model = Notification(
            id=notification.notification_id,
            traveler_id=notification.traveler_id,
            reservation_id=notification.reservation_id,
            payment_id=notification.payment_id,
            channel=notification.channel,
            template_code=notification.template_code,
            status=notification.status.value,
            subject=notification.subject,
            recipient_email=notification.recipient_email,
            recipient_name=notification.recipient_name,
            payload=notification.payload,
            created_at=notification.created_at,
            updated_at=notification.updated_at,
        )
        self.session.add(model)
        self.session.commit()
        self.session.refresh(model)
        return _to_record(model)

    def update(self, notification: NotificationRecord) -> NotificationRecord:
        model = self.session.get(Notification, notification.notification_id)
        assert model is not None
        model.status = notification.status.value
        model.updated_at = notification.updated_at
        self.session.add(model)
        self.session.commit()
        self.session.refresh(model)
        return _to_record(model)

    def get_by_id(self, notification_id: UUID) -> NotificationRecord | None:
        model = self.session.exec(
            select(Notification).where(Notification.id == notification_id)
        ).first()
        return _to_record(model) if model else None
