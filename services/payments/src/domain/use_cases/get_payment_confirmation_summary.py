from uuid import UUID

from adapters.services.confirmation_enrichment import ConfirmationEnrichmentService
from core.config import settings
from domain.ports.payment_checkout_repository import PaymentCheckoutRepository
from domain.ports.payment_repository import PaymentRepository
from domain.schemas.checkout import PaymentConfirmationSummaryResponse
from domain.services.price_breakdown import PriceBreakdown, PriceBreakdownCalculator
from domain.use_cases.base import BaseUseCase
from errors import PaymentNotFoundError


class GetPaymentConfirmationSummaryUseCase(
    BaseUseCase[UUID, PaymentConfirmationSummaryResponse]
):
    def __init__(
        self,
        payment_repository: PaymentRepository,
        checkout_repository: PaymentCheckoutRepository,
        price_calculator: PriceBreakdownCalculator | None = None,
        enrichment_service: ConfirmationEnrichmentService | None = None,
    ):
        self.payment_repository = payment_repository
        self.checkout_repository = checkout_repository
        self.price_calculator = price_calculator or PriceBreakdownCalculator(
            settings.default_tax_rate_by_currency
        )
        self.enrichment_service = enrichment_service or ConfirmationEnrichmentService()

    def execute(self, payment_id: UUID) -> PaymentConfirmationSummaryResponse:
        payment = self.payment_repository.get_by_id(payment_id)
        if payment is None:
            raise PaymentNotFoundError(f"Payment {payment_id} was not found")

        checkout = self.checkout_repository.get_session_by_payment_id(payment_id)
        enrichment = self.enrichment_service.enrich(payment.reservation_id)

        check_in = (checkout.check_in_date if checkout else None) or enrichment.check_in_date
        check_out = (checkout.check_out_date if checkout else None) or enrichment.check_out_date

        breakdown = self.price_calculator.calculate(
            total_in_cents=payment.amount_in_cents,
            currency=payment.currency,
            check_in=check_in,
            check_out=check_out,
        )

        return self._build_response(
            payment, checkout, breakdown, enrichment, check_in, check_out
        )

    @staticmethod
    def _build_response(
        payment,
        checkout,
        breakdown: PriceBreakdown,
        enrichment,
        check_in,
        check_out,
    ) -> PaymentConfirmationSummaryResponse:
        return PaymentConfirmationSummaryResponse(
            payment_id=payment.payment_id,
            reservation_id=payment.reservation_id,
            traveler_id=payment.traveler_id,
            status=payment.status.value,
            amount_in_cents=payment.amount_in_cents,
            currency=payment.currency,
            receipt_id=payment.receipt_id,
            receipt_number=payment.receipt_number,
            property_name=(checkout.property_name if checkout else None)
            or enrichment.property_name,
            property_address=enrichment.property_address,
            check_in_date=check_in,
            check_out_date=check_out,
            guests_count=enrichment.guests_count,
            nights=breakdown.nights,
            nightly_rate_in_cents=breakdown.nightly_rate_in_cents,
            taxes_in_cents=breakdown.taxes_in_cents,
            total_in_cents=breakdown.total_in_cents,
            cancellation_policy=settings.default_cancellation_policy,
        )
