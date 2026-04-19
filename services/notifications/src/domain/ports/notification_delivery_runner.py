from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID


class NotificationDeliveryRunner(ABC):
    @abstractmethod
    def run_delivery(
        self,
        *,
        notification_id: UUID,
        source_ip: str | None = None,
        payment_confirmed_at: datetime | None = None,
    ) -> None:
        raise NotImplementedError
