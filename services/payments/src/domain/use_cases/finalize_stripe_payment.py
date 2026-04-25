from datetime import datetime, timezone

from core.config import settings
from domain.ports.payment_audit_repository import PaymentAuditRepository
from domain.ports.payment_checkout_repository import PaymentCheckoutRepository
from domain.ports.payment_repository import PaymentRepository
from domain.schemas.audit import PaymentAuditLogRecord
from domain.schemas.checkout import PaymentFinalizeRequest, PaymentFinalizeResponse
from domain.services.payment_materializer import (
    build_pending_events,
    build_pending_payment,
)
from domain.use_cases.base import BaseUseCase
from errors import PaymentCheckoutSessionNotFoundError, StripeConfigurationError


class FinalizeStripePaymentUseCase(
    BaseUseCase[PaymentFinalizeRequest, PaymentFinalizeResponse]
):
    def __init__(
        self,
        checkout_repository: PaymentCheckoutRepository,
        payment_repository: PaymentRepository,
        audit_repository: PaymentAuditRepository,
    ):
        self.checkout_repository = checkout_repository
        self.payment_repository = payment_repository
        self.audit_repository = audit_repository

    def execute(
        self,
        payload: PaymentFinalizeRequest,
        source_ip: str | None = None,
    ) -> PaymentFinalizeResponse:
        if not settings.stripe_enabled:
            raise StripeConfigurationError("Stripe test mode is not configured.")

        session = self.checkout_repository.get_session(payload.payment_transaction_id)
        if session is None:
            raise PaymentCheckoutSessionNotFoundError(
                "Payment checkout session not found"
            )

        if session.payment_id is not None:
            return PaymentFinalizeResponse(
                status=session.status,
                payment_id=session.payment_id,
                payment_intent_id=session.payment_intent_id,
                client_secret=session.client_secret,
                error=session.error,
            )

        pending_payment = build_pending_payment(
            session=session,
            confirmation_token_id=payload.confirmation_token_id,
        )
        stored_payment = self.payment_repository.save_payment_result(pending_payment)
        self.payment_repository.add_events(
            stored_payment.payment_id,
            build_pending_events(stored_payment, session),
        )

        now = datetime.now(timezone.utc)
        self.payment_repository.upsert_payment_processing_outbox(
            payment_id=stored_payment.payment_id,
            checkout_session_id=session.payment_transaction_id,
            source_ip=source_ip,
            next_retry_at=now,
            max_attempts=settings.payment_processing_retry_max_attempts,
        )
        self.audit_repository.add_log(
            PaymentAuditLogRecord(
                traveler_id=stored_payment.traveler_id,
                payment_id=stored_payment.payment_id,
                checkout_session_id=session.payment_transaction_id,
                entity_type="payment",
                entity_id=str(stored_payment.payment_id),
                action="payment.finalize.accepted",
                ip_address=source_ip,
                payload={
                    "provider_code": stored_payment.provider_code,
                    "reservation_id": str(stored_payment.reservation_id),
                    "status": stored_payment.status.value,
                    "amount_in_cents": stored_payment.amount_in_cents,
                    "currency": stored_payment.currency,
                    "queued_for_processing": True,
                },
                created_at=now,
            )
        )

        session.confirmation_token_id = payload.confirmation_token_id
        session.payment_id = stored_payment.payment_id
        session.status = "pending"
        session.error = None
        session.updated_at = now
        stored_session = self.checkout_repository.update_session(session)

        return PaymentFinalizeResponse(
            status=stored_session.status,
            payment_id=stored_session.payment_id,
            payment_intent_id=stored_session.payment_intent_id,
            client_secret=stored_session.client_secret,
            error=stored_session.error,
        )
