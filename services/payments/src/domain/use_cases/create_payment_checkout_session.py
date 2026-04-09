from datetime import datetime, timezone
from uuid import uuid4

from core.config import settings
from domain.ports.payment_audit_repository import PaymentAuditRepository
from domain.ports.payment_checkout_repository import PaymentCheckoutRepository
from domain.schemas.audit import PaymentAuditLogRecord
from domain.schemas.checkout import (
    PaymentCheckoutSessionRecord,
    PaymentCheckoutSessionRequest,
    PaymentCheckoutSessionResponse,
)
from domain.use_cases.base import BaseUseCase


class CreatePaymentCheckoutSessionUseCase(
    BaseUseCase[PaymentCheckoutSessionRequest, PaymentCheckoutSessionResponse]
):
    def __init__(
        self,
        repository: PaymentCheckoutRepository,
        audit_repository: PaymentAuditRepository,
    ):
        self.repository = repository
        self.audit_repository = audit_repository

    def execute(
        self,
        payload: PaymentCheckoutSessionRequest,
        source_ip: str | None = None,
    ) -> PaymentCheckoutSessionResponse:
        now = datetime.now(timezone.utc)
        session = PaymentCheckoutSessionRecord(
            payment_transaction_id=uuid4(),
            reservation_id=payload.reservation_id,
            traveler_id=payload.traveler_id,
            provider_code=settings.payment_provider,
            amount_in_cents=payload.amount_in_cents,
            currency=payload.currency,
            property_name=payload.property_name,
            check_in_date=payload.check_in_date,
            check_out_date=payload.check_out_date,
            idempotency_key=f"stripe-checkout-{uuid4()}",
            status="created",
            created_at=now,
            updated_at=now,
        )
        stored = self.repository.create_session(session)
        self.audit_repository.add_log(
            PaymentAuditLogRecord(
                traveler_id=stored.traveler_id,
                checkout_session_id=stored.payment_transaction_id,
                entity_type="payment_checkout_session",
                entity_id=str(stored.payment_transaction_id),
                action="payment.checkout_session.created",
                ip_address=source_ip,
                payload={
                    "provider_code": stored.provider_code,
                    "reservation_id": str(stored.reservation_id),
                    "amount_in_cents": stored.amount_in_cents,
                    "currency": stored.currency,
                    "status": stored.status,
                },
                created_at=now,
            )
        )
        return PaymentCheckoutSessionResponse(
            payment_transaction_id=stored.payment_transaction_id,
            provider_code=stored.provider_code,
            amount_in_cents=stored.amount_in_cents,
            currency=stored.currency,
            publishable_key=settings.stripe_publishable_key,
            stripe_enabled=settings.stripe_enabled,
        )
