from uuid import UUID

from domain.ports.payment_repository import PaymentRepository
from domain.schemas.payment import PaymentPublicResponse
from domain.use_cases.base import BaseUseCase
from errors import PaymentNotFoundError


class GetPaymentUseCase(BaseUseCase[UUID, PaymentPublicResponse]):
    def __init__(self, repository: PaymentRepository):
        self.repository = repository

    def execute(self, payment_id: UUID) -> PaymentPublicResponse:
        payment = self.repository.get_by_id(payment_id)
        if payment is None:
            raise PaymentNotFoundError(f"Payment {payment_id} was not found")

        return PaymentPublicResponse(
            payment_id=payment.payment_id,
            reservation_id=payment.reservation_id,
            status=payment.status,
            amount_in_cents=payment.amount_in_cents,
            currency=payment.currency,
            provider_code=payment.provider_code,
            gateway_charge_id=payment.gateway_charge_id,
            receipt_id=payment.receipt_id,
            receipt_number=payment.receipt_number,
            failure_reason=payment.failure_reason,
        )
