from uuid import UUID

from domain.ports.payment_refund_repository import PaymentRefundRepository
from domain.schemas.payment import PaymentRefundPublicResponse
from domain.use_cases.base import BaseUseCase
from errors import PaymentRefundNotFoundError


class GetPaymentRefundUseCase(BaseUseCase[UUID, PaymentRefundPublicResponse]):
    def __init__(self, refund_repository: PaymentRefundRepository):
        self.refund_repository = refund_repository

    def execute(self, refund_id: UUID) -> PaymentRefundPublicResponse:
        refund = self.refund_repository.get_by_id(refund_id)
        if refund is None:
            raise PaymentRefundNotFoundError(f"Refund {refund_id} was not found")

        return PaymentRefundPublicResponse(
            refund_id=refund.refund_id,
            payment_id=refund.payment_id,
            reservation_id=refund.reservation_id,
            traveler_id=refund.traveler_id,
            amount_in_cents=refund.amount_in_cents,
            currency=refund.currency,
            reason=refund.reason,
            status=refund.status,
            retry_count=refund.retry_count,
            max_attempts=refund.max_attempts,
            sla_deadline_at=refund.sla_deadline_at,
            next_retry_at=refund.next_retry_at,
            last_error=refund.last_error,
            processed_at=refund.processed_at,
            created_at=refund.created_at,
            updated_at=refund.updated_at,
        )
