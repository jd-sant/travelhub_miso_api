from abc import ABC, abstractmethod
from uuid import UUID

from domain.schemas.checkout import PaymentCheckoutSessionRecord


class PaymentCheckoutRepository(ABC):
    @abstractmethod
    def create_session(self, session: PaymentCheckoutSessionRecord) -> PaymentCheckoutSessionRecord:
        pass

    @abstractmethod
    def get_session(self, payment_transaction_id: UUID) -> PaymentCheckoutSessionRecord | None:
        pass

    @abstractmethod
    def get_session_by_payment_intent(self, payment_intent_id: str) -> PaymentCheckoutSessionRecord | None:
        pass

    @abstractmethod
    def update_session(self, session: PaymentCheckoutSessionRecord) -> PaymentCheckoutSessionRecord:
        pass
