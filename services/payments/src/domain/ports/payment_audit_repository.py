from abc import ABC, abstractmethod

from domain.schemas.audit import PaymentAuditLogRecord


class PaymentAuditRepository(ABC):
    @abstractmethod
    def add_log(self, log: PaymentAuditLogRecord) -> None:
        pass
