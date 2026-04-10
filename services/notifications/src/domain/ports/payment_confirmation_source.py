from abc import ABC, abstractmethod
from uuid import UUID

from domain.schemas.notification import PaymentConfirmationSourceRecord


class PaymentConfirmationSource(ABC):
    @abstractmethod
    def get_confirmation(self, payment_id: UUID) -> PaymentConfirmationSourceRecord:
        raise NotImplementedError
