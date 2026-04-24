from datetime import datetime
from uuid import UUID

from domain.ports.payment_repository import PaymentRepository
from domain.schemas.payment import PaymentEventResponse
from domain.use_cases.base import BaseUseCase
from errors import PaymentNotFoundError


class ListPaymentEventsUseCase(BaseUseCase[UUID, list[PaymentEventResponse]]):
    def __init__(self, repository: PaymentRepository):
        self.repository = repository

    def execute(
        self,
        payment_id: UUID,
        *,
        after_created_at: datetime | None = None,
    ) -> list[PaymentEventResponse]:
        if self.repository.get_by_id(payment_id) is None:
            raise PaymentNotFoundError()
        return self.repository.list_events(
            payment_id,
            after_created_at=after_created_at,
        )
