from abc import ABC, abstractmethod
from uuid import UUID

from domain.schemas.notification import NotificationRecord


class NotificationRepository(ABC):
    @abstractmethod
    def create(self, notification: NotificationRecord) -> NotificationRecord:
        raise NotImplementedError

    @abstractmethod
    def update(self, notification: NotificationRecord) -> NotificationRecord:
        raise NotImplementedError

    @abstractmethod
    def get_by_id(self, notification_id: UUID) -> NotificationRecord | None:
        raise NotImplementedError
