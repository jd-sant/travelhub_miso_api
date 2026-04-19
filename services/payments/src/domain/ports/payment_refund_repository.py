from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID

from domain.schemas.payment import PaymentRefundResponse


class PaymentRefundRepository(ABC):
    @abstractmethod
    def find_by_idempotency_key(self, idempotency_key: str) -> PaymentRefundResponse | None:
        pass

    @abstractmethod
    def save_refund(self, refund: PaymentRefundResponse) -> PaymentRefundResponse:
        pass

    @abstractmethod
    def get_by_id(self, refund_id: UUID) -> PaymentRefundResponse | None:
        pass

    @abstractmethod
    def list_due_pending_refunds(self, *, now: datetime, limit: int) -> list[PaymentRefundResponse]:
        pass

    @abstractmethod
    def mark_refund_succeeded(self, *, refund_id: UUID, processed_at: datetime) -> None:
        pass

    @abstractmethod
    def mark_refund_retry(
        self,
        *,
        refund_id: UUID,
        next_retry_at: datetime,
        error_message: str,
        retry_count: int,
        mark_as_failed: bool,
    ) -> None:
        pass

    @abstractmethod
    def count_pending_refunds(self, *, now: datetime) -> int:
        pass
