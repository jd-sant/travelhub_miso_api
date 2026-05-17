from abc import ABC, abstractmethod

from domain.schemas.notification import NotificationDeliveryAttemptRecord


class DeliveryAttemptRepository(ABC):
    @abstractmethod
    def add_attempt(self, attempt: NotificationDeliveryAttemptRecord) -> None:
        raise NotImplementedError
