from abc import ABC, abstractmethod
from uuid import UUID


class ReservationNotificationDispatcher(ABC):
    @abstractmethod
    def dispatch_reservation_update(
        self,
        *,
        traveler_id: UUID,
        reservation_id: UUID,
        status: str,
        reason: str,
        reason_code: str | None = None,
        reason_note: str | None = None,
        source_ip: str | None = None,
        refund_requested: bool = False,
        refund_amount_in_cents: int | None = None,
    ) -> None:
        raise NotImplementedError


class ReservationRefundDispatcher(ABC):
    @abstractmethod
    def request_refund(
        self,
        *,
        reservation_id: UUID,
        cancellation_reason: str,
        source_ip: str | None = None,
    ) -> dict | None:
        raise NotImplementedError
