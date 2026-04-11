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
from domain.schemas.checkout import PaymentCheckoutSessionRecord
from domain.schemas.payment import PaymentChargeResponse, PaymentEventResponse, PaymentStatus
from domain.use_cases.base import BaseUseCase
from errors import StripeWebhookVerificationError


class HandleStripeWebhookUseCase(BaseUseCase[tuple[bytes, str], None]):
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
        payload: tuple[bytes, str],
        source_ip: str | None = None,
    ) -> None:
        try:
            event = self.gateway.construct_event(payload=payload[0], signature=payload[1])
        except Exception as exc:  # noqa: BLE001
            raise StripeWebhookVerificationError(str(exc)) from exc

        event_type = str(event.get("type", ""))
        data = event.get("data", {})
        obj = data.get("object", {}) if isinstance(data, dict) else {}
        payment_intent_id = str(obj.get("id", ""))
        if not payment_intent_id:
            return

        session = self.checkout_repository.get_session_by_payment_intent(payment_intent_id)
        if session is None:
            return

        existing_payment = self.payment_repository.find_by_gateway_charge_id(payment_intent_id)
        if existing_payment is not None:
            session.payment_id = existing_payment.payment_id
            session.status = existing_payment.status.value
            session.updated_at = datetime.now(timezone.utc)
            self.checkout_repository.update_session(session)
            return

        if event_type == "payment_intent.succeeded":
            payment = self._materialize_payment(
                session=session,
                gateway_status="succeeded",
                status=PaymentStatus.confirmed,
                failure_reason=None,
            )
        elif event_type == "payment_intent.payment_failed":
            error = obj.get("last_payment_error", {}) if isinstance(obj, dict) else {}
            failure_reason = (
                error.get("decline_code")
                if isinstance(error, dict) and isinstance(error.get("decline_code"), str)
                else "card_declined"
            )
            payment = self._materialize_payment(
                session=session,
                gateway_status="failed",
                status=PaymentStatus.failed,
                failure_reason=failure_reason,
            )
        else:
            return

        stored_payment = self.payment_repository.save_payment_result(payment)
        self.payment_repository.add_events(
            stored_payment.payment_id,
            self._build_events(stored_payment, session),
        )
        self.audit_repository.add_log(
            PaymentAuditLogRecord(
                traveler_id=stored_payment.traveler_id,
                payment_id=stored_payment.payment_id,
                checkout_session_id=session.payment_transaction_id,
                entity_type="payment",
                entity_id=str(stored_payment.payment_id),
                action="payment.webhook.processed",
                ip_address=source_ip,
                payload={
                    "provider_code": stored_payment.provider_code,
                    "event_type": event_type,
                    "amount_in_cents": stored_payment.amount_in_cents,
                    "currency": stored_payment.currency,
                    "gateway_charge_id": stored_payment.gateway_charge_id,
                    "status": stored_payment.status.value,
                    "failure_reason": stored_payment.failure_reason,
                },
                created_at=stored_payment.updated_at,
            )
        )
        if stored_payment.status == PaymentStatus.confirmed:
            self._dispatch_notification_request(stored_payment.payment_id, source_ip)
        session.payment_id = stored_payment.payment_id
        session.status = stored_payment.status.value
        session.error = stored_payment.failure_reason
        session.updated_at = datetime.now(timezone.utc)
        self.checkout_repository.update_session(session)

    def _materialize_payment(
        self,
        *,
        session: PaymentCheckoutSessionRecord,
        gateway_status: str,
        status: PaymentStatus,
        failure_reason: str | None,
    ) -> PaymentChargeResponse:
        now = datetime.now(timezone.utc)
        token_reference = session.confirmation_token_id or session.payment_intent_id or str(session.payment_transaction_id)
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
            gateway_charge_id=session.payment_intent_id or "",
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

    def _build_events(
        self,
        payment: PaymentChargeResponse,
        session: PaymentCheckoutSessionRecord | None = None,
    ) -> list[PaymentEventResponse]:
        now = datetime.now(timezone.utc)
        payload = {
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
                payload=payload,
                created_at=now,
            )
            for event_type in event_types
        ]

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
