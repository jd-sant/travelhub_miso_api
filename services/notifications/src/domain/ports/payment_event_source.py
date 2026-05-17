from abc import ABC, abstractmethod
from uuid import UUID

from domain.schemas.notification import PaymentPublicSourceRecord, RefundPublicSourceRecord


class PaymentEventSource(ABC):
    @abstractmethod
    def get_payment(self, payment_id: UUID) -> PaymentPublicSourceRecord:
        raise NotImplementedError

    @abstractmethod
    def get_refund(self, refund_id: UUID) -> RefundPublicSourceRecord:
        raise NotImplementedError
