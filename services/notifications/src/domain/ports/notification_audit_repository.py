from abc import ABC, abstractmethod

from domain.schemas.notification import NotificationAuditLogRecord


class NotificationAuditRepository(ABC):
    @abstractmethod
    def add_log(self, log: NotificationAuditLogRecord) -> None:
        raise NotImplementedError
