from datetime import datetime
from uuid import UUID

from sqlmodel import Session, select

from adapters.models.payment_refund import PaymentRefund
from domain.ports.payment_refund_repository import PaymentRefundRepository
from domain.schemas.payment import PaymentRefundResponse, PaymentRefundStatus


def _to_refund_response(model: PaymentRefund) -> PaymentRefundResponse:
    return PaymentRefundResponse(
        refund_id=model.id,
        payment_id=model.payment_id,
        reservation_id=model.reservation_id,
        traveler_id=model.traveler_id,
        amount_in_cents=model.amount_in_cents,
        currency=model.currency,
        reason=model.reason,
        idempotency_key=model.idempotency_key,
        status=PaymentRefundStatus(model.status),
        retry_count=model.retry_count,
        max_attempts=model.max_attempts,
        sla_deadline_at=model.sla_deadline_at,
        next_retry_at=model.next_retry_at,
        last_error=model.last_error,
        processed_at=model.processed_at,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


class SQLModelPaymentRefundRepository(PaymentRefundRepository):
    def __init__(self, session: Session):
        self.session = session

    def find_by_idempotency_key(self, idempotency_key: str) -> PaymentRefundResponse | None:
        model = self.session.exec(
            select(PaymentRefund).where(PaymentRefund.idempotency_key == idempotency_key)
        ).first()
        return _to_refund_response(model) if model else None

    def save_refund(self, refund: PaymentRefundResponse) -> PaymentRefundResponse:
        model = PaymentRefund(
            id=refund.refund_id,
            payment_id=refund.payment_id,
            reservation_id=refund.reservation_id,
            traveler_id=refund.traveler_id,
            amount_in_cents=refund.amount_in_cents,
            currency=refund.currency,
            reason=refund.reason,
            idempotency_key=refund.idempotency_key,
            status=refund.status.value,
            retry_count=refund.retry_count,
            max_attempts=refund.max_attempts,
            sla_deadline_at=refund.sla_deadline_at,
            next_retry_at=refund.next_retry_at,
            last_error=refund.last_error,
            processed_at=refund.processed_at,
            created_at=refund.created_at,
            updated_at=refund.updated_at,
        )
        self.session.add(model)
        self.session.commit()
        self.session.refresh(model)
        return _to_refund_response(model)

    def get_by_id(self, refund_id: UUID) -> PaymentRefundResponse | None:
        model = self.session.get(PaymentRefund, refund_id)
        return _to_refund_response(model) if model else None

    def list_due_pending_refunds(self, *, now: datetime, limit: int) -> list[PaymentRefundResponse]:
        models = self.session.exec(
            select(PaymentRefund)
            .where(PaymentRefund.status == PaymentRefundStatus.pending.value)
            .where(PaymentRefund.next_retry_at <= now)
            .order_by(PaymentRefund.next_retry_at.asc())
            .limit(limit)
        ).all()
        return [_to_refund_response(model) for model in models]

    def mark_refund_succeeded(self, *, refund_id: UUID, processed_at: datetime) -> None:
        model = self.session.get(PaymentRefund, refund_id)
        if model is None:
            return
        model.status = PaymentRefundStatus.succeeded.value
        model.processed_at = processed_at
        model.last_error = None
        model.updated_at = processed_at
        self.session.add(model)
        self.session.commit()

    def mark_refund_retry(
        self,
        *,
        refund_id: UUID,
        next_retry_at: datetime,
        error_message: str,
        retry_count: int,
        mark_as_failed: bool,
    ) -> None:
        model = self.session.get(PaymentRefund, refund_id)
        if model is None:
            return
        model.retry_count = retry_count
        model.next_retry_at = next_retry_at
        model.last_error = error_message
        model.status = (
            PaymentRefundStatus.failed.value
            if mark_as_failed
            else PaymentRefundStatus.pending.value
        )
        model.updated_at = datetime.now(next_retry_at.tzinfo)
        self.session.add(model)
        self.session.commit()

    def count_pending_refunds(self, *, now: datetime) -> int:
        models = self.session.exec(
            select(PaymentRefund)
            .where(PaymentRefund.status == PaymentRefundStatus.pending.value)
            .where(PaymentRefund.next_retry_at <= now)
        ).all()
        return len(models)
