from datetime import datetime, timezone
from uuid import uuid4

from core.config import settings
from domain.ports.payment_audit_repository import PaymentAuditRepository
from domain.ports.payment_repository import PaymentRepository
from domain.ports.stripe_checkout_gateway import StripeCheckoutGateway
from domain.schemas.audit import PaymentAuditLogRecord
from domain.schemas.payment import (
    RefundStatus,
    ReservationRefundRequest,
    ReservationRefundResponse,
)
from domain.use_cases.base import BaseUseCase
from errors import PaymentNotFoundError, RefundNotAvailableError


class CreateReservationRefundUseCase(
    BaseUseCase[ReservationRefundRequest, ReservationRefundResponse]
):
    def __init__(
        self,
        repository: PaymentRepository,
        audit_repository: PaymentAuditRepository,
        gateway: StripeCheckoutGateway,
    ):
        self.repository = repository
        self.audit_repository = audit_repository
        self.gateway = gateway

    def execute(self, payload: ReservationRefundRequest) -> ReservationRefundResponse:
        existing = self.repository.get_refund_by_reservation(payload.reservation_id)
        if existing is not None:
            return existing

        payment = self.repository.find_latest_confirmed_by_reservation(payload.reservation_id)
        if payment is None:
            raise PaymentNotFoundError(
                f"No confirmed payment found for reservation {payload.reservation_id}"
            )
        if not payment.gateway_charge_id:
            raise RefundNotAvailableError(
                "The confirmed payment does not have a refundable gateway identifier."
            )

        now = datetime.now(timezone.utc)
        gateway_refund = (
            self.gateway.create_refund(
                payment_intent_id=payment.gateway_charge_id,
                amount_in_cents=payment.amount_in_cents,
                reason=payload.reason,
                metadata={
                    "payment_id": str(payment.payment_id),
                    "reservation_id": str(payment.reservation_id),
                },
            )
            if settings.payment_provider == "stripe_test" and settings.stripe_enabled
            else {"id": f"fake-refund-{payment.payment_id}"}
        )
        refund = ReservationRefundResponse(
            refund_id=uuid4(),
            payment_id=payment.payment_id,
            reservation_id=payment.reservation_id,
            amount_in_cents=payment.amount_in_cents,
            currency=payment.currency,
            status=RefundStatus.succeeded,
            gateway_refund_id=str(gateway_refund.get("id")) if gateway_refund.get("id") else None,
            created_at=now,
            updated_at=now,
        )
        stored = self.repository.save_refund(refund)
        self.audit_repository.add_log(
            PaymentAuditLogRecord(
                traveler_id=payment.traveler_id,
                payment_id=payment.payment_id,
                checkout_session_id=None,
                entity_type="refund",
                entity_id=str(stored.refund_id),
                action="payment.refund.created",
                ip_address=payload.source_ip,
                payload={
                    "reservation_id": str(payment.reservation_id),
                    "amount_in_cents": stored.amount_in_cents,
                    "currency": stored.currency,
                    "gateway_refund_id": stored.gateway_refund_id,
                    "reason": payload.reason,
                },
                created_at=stored.created_at,
            )
        )
        return stored
