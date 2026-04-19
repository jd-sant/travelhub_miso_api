from abc import ABC, abstractmethod
from decimal import Decimal
from uuid import UUID


class PaymentServiceClient(ABC):
    @abstractmethod
    def request_refund(
        self,
        *,
        reservation_id: UUID,
        amount_in_cents: int,
        reason: str,
        idempotency_key: str,
        source_ip: str | None = None,
    ) -> None:
        pass

    @abstractmethod
    def request_additional_charge(
        self,
        *,
        reservation_id: UUID,
        traveler_id: UUID,
        amount_in_cents: int,
        currency: str,
        idempotency_key: str,
        source_ip: str | None = None,
    ) -> None:
        pass
