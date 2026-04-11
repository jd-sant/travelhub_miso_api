from uuid import UUID

from domain.ports.payment_checkout_repository import PaymentCheckoutRepository
from domain.schemas.checkout import PaymentCheckoutStatusResponse
from domain.use_cases.base import BaseUseCase
from errors import PaymentCheckoutSessionNotFoundError


class GetPaymentCheckoutSessionUseCase(BaseUseCase[UUID, PaymentCheckoutStatusResponse]):
    def __init__(self, repository: PaymentCheckoutRepository):
        self.repository = repository

    def execute(self, payment_transaction_id: UUID) -> PaymentCheckoutStatusResponse:
        session = self.repository.get_session(payment_transaction_id)
        if session is None:
            raise PaymentCheckoutSessionNotFoundError("Payment checkout session not found")

        return PaymentCheckoutStatusResponse(
            payment_transaction_id=session.payment_transaction_id,
            status=session.status,
            payment_id=session.payment_id,
            payment_intent_id=session.payment_intent_id,
            error=session.error,
            updated_at=session.updated_at,
        )
