from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID

from domain.schemas.payment import PaymentChargeResponse, PaymentEventResponse


class PaymentRepository(ABC):
    @abstractmethod
    def find_by_idempotency_key(self, idempotency_key: str) -> PaymentChargeResponse | None:
        pass

    @abstractmethod
    def find_recent_duplicate(
        self,
        *,
        request_fingerprint: str,
        since: datetime,
    ) -> PaymentChargeResponse | None:
        pass

    @abstractmethod
    def save_payment_result(self, payment: PaymentChargeResponse) -> PaymentChargeResponse:
        pass

    @abstractmethod
    def get_by_id(self, payment_id: UUID) -> PaymentChargeResponse | None:
        pass

    @abstractmethod
    def find_by_gateway_charge_id(self, gateway_charge_id: str) -> PaymentChargeResponse | None:
        pass

    @abstractmethod
    def add_events(self, payment_id: UUID, events: list[PaymentEventResponse]) -> None:
        pass

    @abstractmethod
    def list_events(self, payment_id: UUID) -> list[PaymentEventResponse]:
        pass
