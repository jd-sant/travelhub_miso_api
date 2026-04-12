from abc import ABC, abstractmethod
from uuid import UUID


class NotificationDispatcher(ABC):
    @abstractmethod
    def dispatch_payment_confirmation(
        self,
        *,
        payment_id: UUID,
        source_ip: str | None = None,
    ) -> None:
        raise NotImplementedError


class ReservationUpdater(ABC):
    @abstractmethod
    def confirm_reservation(
        self,
        *,
        reservation_id: UUID,
        source_ip: str | None = None,
    ) -> None:
        raise NotImplementedError
