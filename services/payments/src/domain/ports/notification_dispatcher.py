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

    @abstractmethod
    def notify_refund_result(
        self,
        *,
        reservation_id: UUID,
        status: str,
        amount_in_cents: int,
        refund_id: UUID,
        source_ip: str | None = None,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    def notify_additional_charge_result(
        self,
        *,
        reservation_id: UUID,
        status: str,
        amount_in_cents: int,
        payment_id: UUID,
        source_ip: str | None = None,
    ) -> None:
        raise NotImplementedError
