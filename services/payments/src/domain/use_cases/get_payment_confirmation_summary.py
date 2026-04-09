from uuid import UUID

from domain.ports.payment_checkout_repository import PaymentCheckoutRepository
from domain.ports.payment_repository import PaymentRepository
from domain.schemas.checkout import PaymentConfirmationSummaryResponse
from domain.use_cases.base import BaseUseCase
from errors import PaymentNotFoundError


class GetPaymentConfirmationSummaryUseCase(
    BaseUseCase[UUID, PaymentConfirmationSummaryResponse]
):
    def __init__(
        self,
        payment_repository: PaymentRepository,
        checkout_repository: PaymentCheckoutRepository,
    ):
        self.payment_repository = payment_repository
        self.checkout_repository = checkout_repository

    def execute(self, payment_id: UUID) -> PaymentConfirmationSummaryResponse:
        payment = self.payment_repository.get_by_id(payment_id)
        if payment is None:
            raise PaymentNotFoundError(f"Payment {payment_id} was not found")

        checkout_session = self.checkout_repository.get_session_by_payment_id(payment_id)
        return PaymentConfirmationSummaryResponse(
            payment_id=payment.payment_id,
            reservation_id=payment.reservation_id,
            traveler_id=payment.traveler_id,
            status=payment.status.value,
            amount_in_cents=payment.amount_in_cents,
            currency=payment.currency,
            receipt_id=payment.receipt_id,
            receipt_number=payment.receipt_number,
            property_name=checkout_session.property_name if checkout_session else None,
            check_in_date=checkout_session.check_in_date if checkout_session else None,
            check_out_date=checkout_session.check_out_date if checkout_session else None,
        )
