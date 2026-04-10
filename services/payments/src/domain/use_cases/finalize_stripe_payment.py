from datetime import datetime, timezone
from uuid import uuid4

from core.config import settings
from core.security import (
    build_duplicate_guard_key,
    build_payment_fingerprint,
    build_request_checksum,
    hash_token,
)
from domain.ports.payment_audit_repository import PaymentAuditRepository
from domain.ports.payment_checkout_repository import PaymentCheckoutRepository
from domain.ports.notification_dispatcher import NotificationDispatcher
from domain.ports.payment_repository import PaymentRepository
from domain.ports.stripe_checkout_gateway import StripeCheckoutGateway
from domain.schemas.audit import PaymentAuditLogRecord
from domain.schemas.checkout import (
    PaymentCheckoutSessionRecord,
    PaymentFinalizeRequest,
    PaymentFinalizeResponse,
)
from domain.schemas.payment import PaymentChargeResponse, PaymentEventResponse, PaymentStatus
from domain.use_cases.base import BaseUseCase
from errors import (
    PaymentCheckoutSessionNotFoundError,
    StripeConfigurationError,
    StripeIdempotencyConflictError,
    StripePaymentFailureError,
)


class FinalizeStripePaymentUseCase(BaseUseCase[PaymentFinalizeRequest, PaymentFinalizeResponse]):
    def __init__(
        self,
        checkout_repository: PaymentCheckoutRepository,
        payment_repository: PaymentRepository,
        audit_repository: PaymentAuditRepository,
        gateway: StripeCheckoutGateway,
        notification_dispatcher: NotificationDispatcher,
    ):
        self.checkout_repository = checkout_repository
        self.payment_repository = payment_repository
        self.audit_repository = audit_repository
        self.gateway = gateway
        self.notification_dispatcher = notification_dispatcher

    def execute(
        self,
        payload: PaymentFinalizeRequest,
        source_ip: str | None = None,
    ) -> PaymentFinalizeResponse:
        if not settings.stripe_enabled:
            raise StripeConfigurationError("Stripe test mode is not configured.")

        session = self.checkout_repository.get_session(payload.payment_transaction_id)
        if session is None:
            raise PaymentCheckoutSessionNotFoundError("Payment checkout session not found")

        if session.payment_id is not None:
            return PaymentFinalizeResponse(
                status=session.status,
                payment_id=session.payment_id,
                payment_intent_id=session.payment_intent_id,
                client_secret=session.client_secret,
                error=session.error,
            )

        try:
            intent = self.gateway.create_and_confirm_payment(
                amount_in_cents=session.amount_in_cents,
                currency=session.currency,
                confirmation_token_id=payload.confirmation_token_id,
                idempotency_key=session.idempotency_key,
                metadata={
                    "payment_transaction_id": str(session.payment_transaction_id),
                    "reservation_id": str(session.reservation_id),
                    "traveler_id": str(session.traveler_id),
                },
            )
        except StripePaymentFailureError as exc:
            failure_reason = exc.code or "card_declined"
            session.confirmation_token_id = payload.confirmation_token_id
            session.updated_at = datetime.now(timezone.utc)
            payment = self._materialize_payment(
                session=session,
                gateway_charge_id=session.payment_intent_id or "",
                gateway_status="failed",
                token_reference=payload.confirmation_token_id,
                status=PaymentStatus.failed,
                failure_reason=failure_reason,
            )
            stored_payment = self.payment_repository.save_payment_result(payment)
            self.payment_repository.add_events(
                stored_payment.payment_id,
                self._build_events(stored_payment, session),
            )
            self._audit_payment(
                session=session,
                payment=stored_payment,
                action="payment.finalize.failed",
                source_ip=source_ip,
            )
            session.payment_id = stored_payment.payment_id
            session.status = stored_payment.status.value
            session.error = exc.message or failure_reason
            stored_session = self.checkout_repository.update_session(session)
            return PaymentFinalizeResponse(
                status=stored_session.status,
                payment_id=stored_session.payment_id,
                payment_intent_id=stored_session.payment_intent_id,
                client_secret=stored_session.client_secret,
                error=stored_session.error,
            )
        except StripeIdempotencyConflictError:
            existing_session = self.checkout_repository.update_session(session)
            return PaymentFinalizeResponse(
                status=existing_session.status,
                payment_id=existing_session.payment_id,
                payment_intent_id=existing_session.payment_intent_id,
                client_secret=existing_session.client_secret,
                error=existing_session.error or "Duplicate Stripe confirmation attempt.",
            )

        stripe_status = str(intent.get("status", "processing"))
        session.confirmation_token_id = payload.confirmation_token_id
        session.payment_intent_id = str(intent.get("id"))
        session.client_secret = intent.get("client_secret")
        session.updated_at = datetime.now(timezone.utc)

        if stripe_status == "succeeded":
            payment = self._materialize_payment(
                session=session,
                gateway_charge_id=session.payment_intent_id or "",
                gateway_status=stripe_status,
                token_reference=payload.confirmation_token_id,
                status=PaymentStatus.confirmed,
                failure_reason=None,
            )
            stored_payment = self.payment_repository.save_payment_result(payment)
            self.payment_repository.add_events(
                stored_payment.payment_id,
                self._build_events(stored_payment, session),
            )
            self._audit_payment(
                session=session,
                payment=stored_payment,
                action="payment.finalize.confirmed",
                source_ip=source_ip,
            )
            self._dispatch_notification_request(stored_payment.payment_id, source_ip)
            session.payment_id = stored_payment.payment_id
            session.status = stored_payment.status.value
        elif stripe_status in {"requires_payment_method", "canceled"}:
            failure_reason = self._extract_error(intent) or "card_declined"
            payment = self._materialize_payment(
                session=session,
                gateway_charge_id=session.payment_intent_id or "",
                gateway_status=stripe_status,
                token_reference=payload.confirmation_token_id,
                status=PaymentStatus.failed,
                failure_reason=failure_reason,
            )
            stored_payment = self.payment_repository.save_payment_result(payment)
            self.payment_repository.add_events(
                stored_payment.payment_id,
                self._build_events(stored_payment, session),
            )
            self._audit_payment(
                session=session,
                payment=stored_payment,
                action="payment.finalize.failed",
                source_ip=source_ip,
            )
            session.payment_id = stored_payment.payment_id
            session.status = stored_payment.status.value
            session.error = failure_reason
        else:
            session.status = stripe_status
            self.audit_repository.add_log(
                PaymentAuditLogRecord(
                    traveler_id=session.traveler_id,
                    checkout_session_id=session.payment_transaction_id,
                    entity_type="payment_checkout_session",
                    entity_id=str(session.payment_transaction_id),
                    action="payment.finalize.requires_action",
                    ip_address=source_ip,
                    payload={
                        "provider_code": session.provider_code,
                        "payment_intent_id": session.payment_intent_id,
                        "status": stripe_status,
                    },
                    created_at=session.updated_at,
                )
            )

        stored_session = self.checkout_repository.update_session(session)
        return PaymentFinalizeResponse(
            status=stored_session.status,
            payment_id=stored_session.payment_id,
            payment_intent_id=stored_session.payment_intent_id,
            client_secret=stored_session.client_secret,
            error=stored_session.error,
        )

    def _materialize_payment(
        self,
        *,
        session: PaymentCheckoutSessionRecord,
        gateway_charge_id: str,
        gateway_status: str,
        token_reference: str,
        status: PaymentStatus,
        failure_reason: str | None,
    ) -> PaymentChargeResponse:
        now = datetime.now(timezone.utc)
        token_hash = hash_token(token_reference)
        request_fingerprint = build_payment_fingerprint(
            reservation_id=str(session.reservation_id),
            traveler_id=str(session.traveler_id),
            amount_in_cents=session.amount_in_cents,
            currency=session.currency,
            token_hash=token_hash,
        )
        duplicate_guard_key = build_duplicate_guard_key(
            request_fingerprint=request_fingerprint,
            bucket=int(now.timestamp() // settings.payment_duplicate_window_seconds),
        )
        request_checksum = build_request_checksum(
            "|".join(
                [
                    str(session.reservation_id),
                    str(session.traveler_id),
                    str(session.amount_in_cents),
                    session.currency,
                    token_reference,
                    session.idempotency_key,
                ]
            ),
            settings.payment_integrity_secret,
        )

        payment = PaymentChargeResponse(
            payment_id=uuid4(),
            reservation_id=session.reservation_id,
            traveler_id=session.traveler_id,
            provider_code=session.provider_code,
            status=status,
            amount_in_cents=session.amount_in_cents,
            currency=session.currency,
            gateway_charge_id=gateway_charge_id,
            gateway_status=gateway_status,
            idempotency_key=session.idempotency_key,
            request_fingerprint=request_fingerprint,
            duplicate_guard_key=duplicate_guard_key,
            request_checksum=request_checksum,
            payment_method_token_hash=token_hash,
            failure_reason=failure_reason,
            card_brand="visa" if status == PaymentStatus.confirmed else None,
            card_last4="4242" if status == PaymentStatus.confirmed else None,
            created_at=now,
            updated_at=now,
        )
        if status == PaymentStatus.confirmed:
            payment.receipt_id = uuid4()
            payment.receipt_number = now.strftime("RCPT-%Y%m%d-%H%M%S")
        return payment

    def _build_events(self, payment: PaymentChargeResponse, session: PaymentCheckoutSessionRecord | None = None) -> list[PaymentEventResponse]:
        now = datetime.now(timezone.utc)
        base_payload = {
            "payment_id": str(payment.payment_id),
            "reservation_id": str(payment.reservation_id),
            "traveler_id": str(payment.traveler_id),
            "amount_in_cents": payment.amount_in_cents,
            "currency": payment.currency,
            "gateway_charge_id": payment.gateway_charge_id,
            "receipt_id": str(payment.receipt_id) if payment.receipt_id else None,
            "receipt_number": payment.receipt_number,
            "status": payment.status.value,
            "failure_reason": payment.failure_reason,
            "property_name": session.property_name if session else None,
            "check_in_date": session.check_in_date.isoformat() if session and session.check_in_date else None,
            "check_out_date": session.check_out_date.isoformat() if session and session.check_out_date else None,
        }
        event_types = (
            [
                "payment.succeeded",
                "reservation.confirmation.requested",
                "notification.payment_confirmation.requested",
                "inventory.update.requested",
                "receipt.generated",
            ]
            if payment.status == PaymentStatus.confirmed
            else ["payment.failed"]
        )
        return [
            PaymentEventResponse(
                event_id=uuid4(),
                payment_id=payment.payment_id,
                event_type=event_type,
                payload=base_payload,
                created_at=now,
            )
            for event_type in event_types
        ]

    def _extract_error(self, intent: dict) -> str | None:
        error = intent.get("last_payment_error")
        if isinstance(error, dict):
            if isinstance(error.get("decline_code"), str):
                return str(error["decline_code"])
            if isinstance(error.get("code"), str):
                return str(error["code"])
            if isinstance(error.get("message"), str):
                return str(error["message"])
        return None

    def _audit_payment(
        self,
        *,
        session: PaymentCheckoutSessionRecord,
        payment: PaymentChargeResponse,
        action: str,
        source_ip: str | None = None,
    ) -> None:
        self.audit_repository.add_log(
            PaymentAuditLogRecord(
                traveler_id=payment.traveler_id,
                payment_id=payment.payment_id,
                checkout_session_id=session.payment_transaction_id,
                entity_type="payment",
                entity_id=str(payment.payment_id),
                action=action,
                ip_address=source_ip,
                payload={
                    "provider_code": payment.provider_code,
                    "reservation_id": str(payment.reservation_id),
                    "status": payment.status.value,
                    "gateway_charge_id": payment.gateway_charge_id,
                    "failure_reason": payment.failure_reason,
                },
                created_at=payment.updated_at,
            )
        )

    def _dispatch_notification_request(
        self,
        payment_id,
        source_ip: str | None,
    ) -> None:
        try:
            self.notification_dispatcher.dispatch_payment_confirmation(
                payment_id=payment_id,
                source_ip=source_ip,
            )
            self.audit_repository.add_log(
                PaymentAuditLogRecord(
                    payment_id=payment_id,
                    entity_type="payment",
                    entity_id=str(payment_id),
                    action="notification.payment_confirmation.requested",
                    ip_address=source_ip,
                    payload={"dispatch_status": "requested"},
                    created_at=datetime.now(timezone.utc),
                )
            )
        except Exception as exc:  # noqa: BLE001
            self.audit_repository.add_log(
                PaymentAuditLogRecord(
                    payment_id=payment_id,
                    entity_type="payment",
                    entity_id=str(payment_id),
                    action="notification.payment_confirmation.dispatch_failed",
                    ip_address=source_ip,
                    payload={"error": str(exc)},
                    created_at=datetime.now(timezone.utc),
                )
            )
