from domain.schemas.payment import (
    AdditionalChargeRequest,
    PaymentChargeRequest,
    PaymentPublicResponse,
)
from domain.use_cases.base import BaseUseCase
from domain.use_cases.create_payment_charge import CreatePaymentChargeUseCase


class CreateAdditionalChargeForReservationUseCase(
    BaseUseCase[AdditionalChargeRequest, PaymentPublicResponse]
):
    def __init__(
        self,
        create_payment_charge_use_case: CreatePaymentChargeUseCase,
    ):
        self.create_payment_charge_use_case = create_payment_charge_use_case

    def execute(
        self,
        payload: AdditionalChargeRequest,
        source_ip: str | None = None,
    ) -> PaymentPublicResponse:
        return self.create_payment_charge_use_case.execute(
            PaymentChargeRequest(
                reservation_id=payload.reservation_id,
                traveler_id=payload.traveler_id,
                payment_method_token=payload.payment_method_token,
                amount_in_cents=payload.amount_in_cents,
                currency=payload.currency,
                idempotency_key=payload.idempotency_key,
            ),
            source_ip=source_ip,
        )
