from domain.ports.payment_repository import PaymentRepository
from domain.schemas.payment import (
    PaymentRefundCreateRequest,
    PaymentRefundPublicResponse,
    ReservationPaymentRefundRequest,
)
from domain.use_cases.base import BaseUseCase
from domain.use_cases.create_payment_refund import CreatePaymentRefundUseCase
from errors import PaymentNotFoundError


class CreateRefundForReservationUseCase(
    BaseUseCase[ReservationPaymentRefundRequest, PaymentRefundPublicResponse]
):
    def __init__(
        self,
        payment_repository: PaymentRepository,
        create_payment_refund_use_case: CreatePaymentRefundUseCase,
    ):
        self.payment_repository = payment_repository
        self.create_payment_refund_use_case = create_payment_refund_use_case

    def execute(
        self,
        payload: ReservationPaymentRefundRequest,
        source_ip: str | None = None,
        correlation_id: str | None = None,
    ) -> PaymentRefundPublicResponse:
        payment = self.payment_repository.find_latest_confirmed_by_reservation_id(
            payload.reservation_id
        )
        if payment is None:
            raise PaymentNotFoundError(
                f"No confirmed payment found for reservation {payload.reservation_id}"
            )

        return self.create_payment_refund_use_case.execute(
            PaymentRefundCreateRequest(
                payment_id=payment.payment_id,
                amount_in_cents=payload.amount_in_cents,
                reason=payload.reason,
                idempotency_key=payload.idempotency_key,
            ),
            source_ip=source_ip,
            correlation_id=correlation_id,
        )
