from datetime import datetime
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from adapters.models.payment import Payment
from adapters.models.payment_event import PaymentEvent
from adapters.models.payment_reservation_confirmation_outbox import (
    PaymentReservationConfirmationOutbox,
)
from domain.ports.payment_repository import PaymentRepository
from domain.schemas.payment import (
    PaymentChargeResponse,
    PaymentEventResponse,
    PaymentStatus,
    ReservationConfirmationOutboxRecord,
    ReservationConfirmationOutboxStatus,
)


def _to_payment_response(model: Payment) -> PaymentChargeResponse:
    return PaymentChargeResponse(
        payment_id=model.id,
        reservation_id=model.reservation_id,
        traveler_id=model.traveler_id,
        provider_code=model.provider_code,
        status=PaymentStatus(model.status),
        amount_in_cents=model.amount_in_cents,
        currency=model.currency,
        gateway_charge_id=model.gateway_charge_id,
        gateway_status=model.gateway_status,
        idempotency_key=model.idempotency_key,
        request_fingerprint=model.request_fingerprint,
        duplicate_guard_key=model.duplicate_guard_key,
        request_checksum=model.request_checksum,
        payment_method_token_hash=model.payment_method_token_hash,
        receipt_id=model.receipt_id,
        receipt_number=model.receipt_number,
        failure_reason=model.failure_reason,
        card_brand=model.card_brand,
        card_last4=model.card_last4,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _to_event_response(model: PaymentEvent) -> PaymentEventResponse:
    return PaymentEventResponse(
        event_id=model.id,
        payment_id=model.payment_id,
        event_type=model.event_type,
        payload=model.payload,
        created_at=model.created_at,
    )


def _to_outbox_response(
    model: PaymentReservationConfirmationOutbox,
) -> ReservationConfirmationOutboxRecord:
    return ReservationConfirmationOutboxRecord(
        outbox_id=model.id,
        payment_id=model.payment_id,
        reservation_id=model.reservation_id,
        status=ReservationConfirmationOutboxStatus(model.status),
        attempt_count=model.attempt_count,
        max_attempts=model.max_attempts,
        next_retry_at=model.next_retry_at,
        last_error=model.last_error,
        last_attempt_at=model.last_attempt_at,
        processed_at=model.processed_at,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


class SQLModelPaymentRepository(PaymentRepository):
    def __init__(self, session: Session):
        self.session = session

    def find_by_idempotency_key(self, idempotency_key: str) -> PaymentChargeResponse | None:
        model = self.session.exec(
            select(Payment).where(Payment.idempotency_key == idempotency_key)
        ).first()
        return _to_payment_response(model) if model else None

    def find_recent_duplicate(
        self,
        *,
        request_fingerprint: str,
        since: datetime,
    ) -> PaymentChargeResponse | None:
        model = self.session.exec(
            select(Payment)
            .where(Payment.request_fingerprint == request_fingerprint)
            .where(Payment.created_at >= since)
            .order_by(Payment.created_at.desc())
        ).first()
        return _to_payment_response(model) if model else None

    def save_payment_result(self, payment: PaymentChargeResponse) -> PaymentChargeResponse:
        model = Payment(
            id=payment.payment_id,
            reservation_id=payment.reservation_id,
            traveler_id=payment.traveler_id,
            provider_code=payment.provider_code,
            status=payment.status.value,
            amount_in_cents=payment.amount_in_cents,
            currency=payment.currency,
            payment_method_token_hash=payment.payment_method_token_hash,
            request_fingerprint=payment.request_fingerprint,
            duplicate_guard_key=payment.duplicate_guard_key,
            request_checksum=payment.request_checksum,
            idempotency_key=payment.idempotency_key,
            gateway_charge_id=payment.gateway_charge_id,
            gateway_status=payment.gateway_status,
            failure_reason=payment.failure_reason,
            card_brand=payment.card_brand,
            card_last4=payment.card_last4,
            receipt_id=payment.receipt_id,
            receipt_number=payment.receipt_number,
            created_at=payment.created_at,
            updated_at=payment.updated_at,
        )
        self.session.add(model)
        try:
            self.session.commit()
            self.session.refresh(model)
        except IntegrityError:
            self.session.rollback()
            raise
        return _to_payment_response(model)

    def get_by_id(self, payment_id: UUID) -> PaymentChargeResponse | None:
        model = self.session.get(Payment, payment_id)
        return _to_payment_response(model) if model else None

    def find_by_gateway_charge_id(self, gateway_charge_id: str) -> PaymentChargeResponse | None:
        model = self.session.exec(
            select(Payment).where(Payment.gateway_charge_id == gateway_charge_id)
        ).first()
        return _to_payment_response(model) if model else None

    def find_latest_confirmed_by_reservation_id(
        self,
        reservation_id: UUID,
    ) -> PaymentChargeResponse | None:
        model = self.session.exec(
            select(Payment)
            .where(Payment.reservation_id == reservation_id)
            .where(Payment.status == PaymentStatus.confirmed.value)
            .order_by(Payment.created_at.desc())
        ).first()
        return _to_payment_response(model) if model else None

    def add_events(self, payment_id: UUID, events: list[PaymentEventResponse]) -> None:
        for event in events:
            model = PaymentEvent(
                id=event.event_id,
                payment_id=payment_id,
                event_type=event.event_type,
                payload=event.payload,
                created_at=event.created_at,
            )
            self.session.add(model)
        self.session.commit()

    def list_events(self, payment_id: UUID) -> list[PaymentEventResponse]:
        models = self.session.exec(
            select(PaymentEvent)
            .where(PaymentEvent.payment_id == payment_id)
            .order_by(PaymentEvent.created_at.asc())
        ).all()
        return [_to_event_response(model) for model in models]

    def upsert_reservation_confirmation_outbox_failure(
        self,
        *,
        payment_id: UUID,
        reservation_id: UUID,
        error_message: str,
        next_retry_at: datetime,
        max_attempts: int,
    ) -> None:
        model = self.session.exec(
            select(PaymentReservationConfirmationOutbox).where(
                PaymentReservationConfirmationOutbox.payment_id == payment_id
            )
        ).first()

        if model is None:
            model = PaymentReservationConfirmationOutbox(
                payment_id=payment_id,
                reservation_id=reservation_id,
                status="pending",
                attempt_count=1,
                max_attempts=max_attempts,
                next_retry_at=next_retry_at,
                last_error=error_message,
                last_attempt_at=datetime.now(next_retry_at.tzinfo),
                created_at=datetime.now(next_retry_at.tzinfo),
                updated_at=datetime.now(next_retry_at.tzinfo),
            )
            self.session.add(model)
        else:
            model.status = "pending"
            model.reservation_id = reservation_id
            model.max_attempts = max_attempts
            model.last_error = error_message
            model.next_retry_at = next_retry_at
            model.last_attempt_at = datetime.now(next_retry_at.tzinfo)
            model.updated_at = datetime.now(next_retry_at.tzinfo)
            self.session.add(model)
        self.session.commit()

    def list_due_reservation_confirmation_outbox(
        self,
        *,
        now: datetime,
        limit: int,
    ) -> list[ReservationConfirmationOutboxRecord]:
        models = self.session.exec(
            select(PaymentReservationConfirmationOutbox)
            .where(PaymentReservationConfirmationOutbox.status == "pending")
            .where(PaymentReservationConfirmationOutbox.next_retry_at <= now)
            .order_by(PaymentReservationConfirmationOutbox.next_retry_at.asc())
            .limit(limit)
        ).all()
        return [_to_outbox_response(model) for model in models]

    def mark_reservation_confirmation_outbox_succeeded(
        self,
        *,
        outbox_id: UUID,
        processed_at: datetime,
    ) -> None:
        model = self.session.get(PaymentReservationConfirmationOutbox, outbox_id)
        if model is None:
            return
        model.status = "succeeded"
        model.processed_at = processed_at
        model.last_attempt_at = processed_at
        model.updated_at = processed_at
        self.session.add(model)
        self.session.commit()

    def mark_reservation_confirmation_outbox_retry(
        self,
        *,
        outbox_id: UUID,
        next_retry_at: datetime,
        error_message: str,
        attempt_count: int,
        mark_as_failed: bool,
    ) -> None:
        model = self.session.get(PaymentReservationConfirmationOutbox, outbox_id)
        if model is None:
            return
        model.attempt_count = attempt_count
        model.last_error = error_message
        model.next_retry_at = next_retry_at
        model.last_attempt_at = datetime.now(next_retry_at.tzinfo)
        model.status = "failed" if mark_as_failed else "pending"
        model.updated_at = datetime.now(next_retry_at.tzinfo)
        self.session.add(model)
        self.session.commit()

    def count_reservation_confirmation_outbox_pending(self, *, now: datetime) -> int:
        models = self.session.exec(
            select(PaymentReservationConfirmationOutbox)
            .where(PaymentReservationConfirmationOutbox.status == "pending")
            .where(PaymentReservationConfirmationOutbox.next_retry_at <= now)
        ).all()
        return len(models)
