from datetime import datetime, timedelta, timezone
from uuid import uuid4

from domain.ports.payment_audit_repository import PaymentAuditRepository
from domain.ports.payment_refund_repository import PaymentRefundRepository
from domain.ports.payment_repository import PaymentRepository
from domain.schemas.audit import PaymentAuditLogRecord
from domain.schemas.payment import (
    PaymentEventResponse,
    PaymentRefundCreateRequest,
    PaymentRefundPublicResponse,
    PaymentRefundResponse,
    PaymentRefundStatus,
    PaymentStatus,
)
from domain.use_cases.base import BaseUseCase
from errors import InvalidRefundAmountError, PaymentNotFoundError, PaymentRefundNotAllowedError
from core.config import settings


class CreatePaymentRefundUseCase(
    BaseUseCase[PaymentRefundCreateRequest, PaymentRefundPublicResponse]
):
    def __init__(
        self,
        payment_repository: PaymentRepository,
        refund_repository: PaymentRefundRepository,
        audit_repository: PaymentAuditRepository,
    ):
        self.payment_repository = payment_repository
        self.refund_repository = refund_repository
        self.audit_repository = audit_repository

    def execute(
        self,
        payload: PaymentRefundCreateRequest,
        source_ip: str | None = None,
    ) -> PaymentRefundPublicResponse:
        existing_refund = self.refund_repository.find_by_idempotency_key(payload.idempotency_key)
        if existing_refund is not None:
            return self._to_public_response(existing_refund)

        payment = self.payment_repository.get_by_id(payload.payment_id)
        if payment is None:
            raise PaymentNotFoundError(f"Payment {payload.payment_id} was not found")

        if payment.status != PaymentStatus.confirmed:
            raise PaymentRefundNotAllowedError("Refunds only allowed for confirmed payments")

        if payload.amount_in_cents > payment.amount_in_cents:
            raise InvalidRefundAmountError("Refund amount exceeds original charge")

        now = datetime.now(timezone.utc)
        refund = PaymentRefundResponse(
            refund_id=uuid4(),
            payment_id=payment.payment_id,
            reservation_id=payment.reservation_id,
            traveler_id=payment.traveler_id,
            amount_in_cents=payload.amount_in_cents,
            currency=payment.currency,
            reason=payload.reason,
            idempotency_key=payload.idempotency_key,
            status=PaymentRefundStatus.pending,
            retry_count=0,
            max_attempts=settings.refund_retry_max_attempts,
            sla_deadline_at=now + timedelta(minutes=settings.refund_sla_minutes),
            next_retry_at=now,
            created_at=now,
            updated_at=now,
        )

        stored_refund = self.refund_repository.save_refund(refund)
        self.payment_repository.add_events(
            payment.payment_id,
            [
                PaymentEventResponse(
                    event_id=uuid4(),
                    payment_id=payment.payment_id,
                    event_type="payment.refund.requested",
                    payload={
                        "refund_id": str(stored_refund.refund_id),
                        "amount_in_cents": stored_refund.amount_in_cents,
                        "currency": stored_refund.currency,
                        "reason": stored_refund.reason,
                        "status": stored_refund.status.value,
                    },
                    created_at=now,
                )
            ],
        )
        self.audit_repository.add_log(
            PaymentAuditLogRecord(
                traveler_id=payment.traveler_id,
                payment_id=payment.payment_id,
                entity_type="payment_refund",
                entity_id=str(stored_refund.refund_id),
                action="payment.refund.requested",
                ip_address=source_ip,
                payload={
                    "payment_id": str(payment.payment_id),
                    "reservation_id": str(payment.reservation_id),
                    "amount_in_cents": stored_refund.amount_in_cents,
                    "currency": stored_refund.currency,
                    "reason": stored_refund.reason,
                    "status": stored_refund.status.value,
                },
                created_at=now,
            )
        )
        return self._to_public_response(stored_refund)

    def _to_public_response(self, refund: PaymentRefundResponse) -> PaymentRefundPublicResponse:
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
