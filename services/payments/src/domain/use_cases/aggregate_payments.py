from datetime import datetime
from uuid import UUID

from domain.ports.payment_repository import PaymentRepository
from domain.schemas.payment import PaymentAggregateResponse, PaymentStatus


class AggregatePaymentsUseCase:
    def __init__(self, repository: PaymentRepository):
        self.repository = repository

    def execute(
        self,
        reservation_ids: list[UUID],
        *,
        status: PaymentStatus = PaymentStatus.confirmed,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        granularity: str | None = None,
    ) -> PaymentAggregateResponse:
        return self.repository.aggregate_by_reservations(
            reservation_ids,
            status=status,
            start_date=start_date,
            end_date=end_date,
            granularity=granularity,
        )
