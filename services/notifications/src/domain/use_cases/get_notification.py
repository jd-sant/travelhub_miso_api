from uuid import UUID

from core.privacy import mask_email
from domain.ports.notification_repository import NotificationRepository
from domain.schemas.notification import NotificationResponse
from domain.use_cases.base import BaseUseCase
from errors import NotificationNotFoundError


class GetNotificationUseCase(BaseUseCase[UUID, NotificationResponse]):
    def __init__(self, repository: NotificationRepository):
        self.repository = repository

    def execute(self, notification_id: UUID) -> NotificationResponse:
        notification = self.repository.get_by_id(notification_id)
        if notification is None:
            raise NotificationNotFoundError(f"Notification {notification_id} was not found")
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
