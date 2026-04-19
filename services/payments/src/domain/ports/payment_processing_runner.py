from abc import ABC, abstractmethod
from uuid import UUID


class PaymentProcessingRunner(ABC):
    @abstractmethod
    def run_checkout_processing(
        self,
        *,
        payment_transaction_id: UUID,
        source_ip: str | None = None,
    ) -> None:
        pass
