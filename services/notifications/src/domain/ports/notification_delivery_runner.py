from abc import ABC, abstractmethod
from uuid import UUID


class NotificationDeliveryRunner(ABC):
    @abstractmethod
    def run_delivery(
        self,
        *,
        notification_id: UUID,
        source_ip: str | None = None,
    ) -> None:
        raise NotImplementedError
