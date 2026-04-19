from datetime import datetime, timedelta, timezone
from uuid import UUID

from core.config import settings
from domain.ports.notification_dispatcher import (
    NotificationDispatcher,
    ReservationUpdater,
)
from domain.ports.payment_audit_repository import PaymentAuditRepository
from domain.ports.payment_checkout_repository import PaymentCheckoutRepository
from domain.ports.payment_repository import PaymentRepository
from domain.ports.stripe_checkout_gateway import StripeCheckoutGateway
from domain.schemas.audit import PaymentAuditLogRecord
from domain.schemas.payment import (
    PaymentChargeResponse,
    PaymentProcessingOutboxRecord,
    PaymentProcessingRetryResponse,
    PaymentStatus,
)
from domain.services.payment_materializer import (
    apply_gateway_result,
    build_intermediate_event,
    build_processing_started_event,
    build_terminal_events,
)
from domain.use_cases.base import BaseUseCase
from errors import StripeIdempotencyConflictError, StripePaymentFailureError


class ProcessQueuedPaymentsUseCase(
    BaseUseCase[UUID | int | None, PaymentProcessingRetryResponse]
):
    def __init__(
        self,
        payment_repository: PaymentRepository,
        checkout_repository: PaymentCheckoutRepository,
        audit_repository: PaymentAuditRepository,
        gateway: StripeCheckoutGateway,
        notification_dispatcher: NotificationDispatcher,
        reservation_updater: ReservationUpdater,
    ):
        self.payment_repository = payment_repository
        self.checkout_repository = checkout_repository
        self.audit_repository = audit_repository
        self.gateway = gateway
        self.notification_dispatcher = notification_dispatcher
        self.reservation_updater = reservation_updater

    def execute(
        self,
        payload: UUID | int | None = None,
        source_ip: str | None = None,
    ) -> PaymentProcessingRetryResponse:
        now = datetime.now(timezone.utc)
        items = self._resolve_items(payload, now)

        processed_count = 0
        succeeded_count = 0
        failed_count = 0

        for item in items:
            processed_count += 1
            result = self._process_item(item, source_ip=source_ip or item.source_ip)
            if result == "succeeded":
                succeeded_count += 1
            elif result == "failed":
                failed_count += 1

        pending_count = self.payment_repository.count_payment_processing_outbox_pending(
            now=datetime.now(timezone.utc)
        )
        return PaymentProcessingRetryResponse(
            processed_count=processed_count,
            succeeded_count=succeeded_count,
            failed_count=failed_count,
            pending_count=pending_count,
        )

    def _resolve_items(
        self,
        payload: UUID | int | None,
        now: datetime,
    ) -> list[PaymentProcessingOutboxRecord]:
        if isinstance(payload, UUID):
            session = self.checkout_repository.get_session(payload)
            if session is None or session.payment_id is None:
                return []
            item = self.payment_repository.get_payment_processing_outbox(
                payment_id=session.payment_id
            )
            return [item] if item is not None else []

        limit = payload or settings.payment_processing_retry_batch_size
        return self.payment_repository.list_due_payment_processing_outbox(
            now=now,
            limit=limit,
        )

    def _process_item(
        self,
        item: PaymentProcessingOutboxRecord,
        *,
        source_ip: str | None,
    ) -> str:
        payment = self.payment_repository.get_by_id(item.payment_id)
        session = self.checkout_repository.get_session_by_payment_id(item.payment_id)
        now = datetime.now(timezone.utc)

        if payment is None or session is None:
            self._mark_processing_retry(
                item=item,
                now=now,
                error_message="Missing payment or checkout session for queued processing.",
                source_ip=source_ip,
            )
            return "failed"

        if payment.status in {PaymentStatus.confirmed, PaymentStatus.failed}:
            self.payment_repository.mark_payment_processing_outbox_succeeded(
                outbox_id=item.outbox_id,
                processed_at=now,
            )
            return "succeeded"

        attempt_count = item.attempt_count + 1
        self.payment_repository.mark_payment_processing_outbox_processing(
            outbox_id=item.outbox_id,
            attempt_count=attempt_count,
            processing_started_at=now,
        )

        payment = payment.model_copy(
            update={
                "gateway_status": "processing",
                "updated_at": now,
            }
        )
        session.status = "processing"
        session.updated_at = now
        self.payment_repository.save_payment_result(payment)
        self.checkout_repository.update_session(session)
        self.payment_repository.add_events(
            payment.payment_id,
            [build_processing_started_event(payment, session)],
        )
        self.audit_repository.add_log(
            PaymentAuditLogRecord(
                traveler_id=payment.traveler_id,
                payment_id=payment.payment_id,
                checkout_session_id=session.payment_transaction_id,
                entity_type="payment",
                entity_id=str(payment.payment_id),
                action="payment.processing.started",
                ip_address=source_ip,
                payload={
                    "reservation_id": str(payment.reservation_id),
                    "provider_code": payment.provider_code,
                    "attempt_count": attempt_count,
                    "amount_in_cents": payment.amount_in_cents,
                    "currency": payment.currency,
                },
                created_at=now,
            )
        )

        try:
            intent = self.gateway.create_and_confirm_payment(
                amount_in_cents=session.amount_in_cents,
                currency=session.currency,
                confirmation_token_id=session.confirmation_token_id or "",
                idempotency_key=session.idempotency_key,
                metadata={
                    "payment_id": str(payment.payment_id),
                    "payment_transaction_id": str(session.payment_transaction_id),
                    "reservation_id": str(session.reservation_id),
                    "traveler_id": str(session.traveler_id),
                },
            )
        except StripeIdempotencyConflictError as exc:
            self._mark_processing_retry(
                item=item,
                now=now,
                error_message=str(exc) or "Duplicate Stripe confirmation attempt.",
                source_ip=source_ip,
                attempt_count=attempt_count,
            )
            session.status = "pending"
            session.error = str(exc) or "Duplicate Stripe confirmation attempt."
            session.updated_at = now
            self.checkout_repository.update_session(session)
            return "failed"
        except StripePaymentFailureError as exc:
            failure_reason = exc.code or "card_declined"
            failed_payment = apply_gateway_result(
                payment=payment,
                gateway_charge_id=session.payment_intent_id,
                gateway_status="failed",
                status=PaymentStatus.failed,
                failure_reason=failure_reason,
            )
            self.payment_repository.save_payment_result(failed_payment)
            self.payment_repository.add_events(
                failed_payment.payment_id,
                build_terminal_events(failed_payment, session),
            )
            session.status = "failed"
            session.error = exc.message or failure_reason
            session.updated_at = failed_payment.updated_at
            self.checkout_repository.update_session(session)
            self.audit_repository.add_log(
                PaymentAuditLogRecord(
                    traveler_id=failed_payment.traveler_id,
                    payment_id=failed_payment.payment_id,
                    checkout_session_id=session.payment_transaction_id,
                    entity_type="payment",
                    entity_id=str(failed_payment.payment_id),
                    action="payment.processing.failed",
                    ip_address=source_ip,
                    payload={
                        "reservation_id": str(failed_payment.reservation_id),
                        "status": failed_payment.status.value,
                        "gateway_status": failed_payment.gateway_status,
                        "failure_reason": failed_payment.failure_reason,
                    },
                    created_at=failed_payment.updated_at,
                )
            )
            self.payment_repository.mark_payment_processing_outbox_succeeded(
                outbox_id=item.outbox_id,
                processed_at=failed_payment.updated_at,
            )
            return "succeeded"

        stripe_status = str(intent.get("status", "processing"))
        session.payment_intent_id = str(intent.get("id"))
        session.client_secret = intent.get("client_secret")

        if stripe_status == "succeeded":
            confirmed_payment = apply_gateway_result(
                payment=payment,
                gateway_charge_id=session.payment_intent_id,
                gateway_status=stripe_status,
                status=PaymentStatus.confirmed,
                failure_reason=None,
            )
            self.payment_repository.save_payment_result(confirmed_payment)
            self.payment_repository.add_events(
                confirmed_payment.payment_id,
                build_terminal_events(confirmed_payment, session),
            )
            session.status = "confirmed"
            session.error = None
            session.updated_at = confirmed_payment.updated_at
            self.checkout_repository.update_session(session)
            self.audit_repository.add_log(
                PaymentAuditLogRecord(
                    traveler_id=confirmed_payment.traveler_id,
                    payment_id=confirmed_payment.payment_id,
                    checkout_session_id=session.payment_transaction_id,
                    entity_type="payment",
                    entity_id=str(confirmed_payment.payment_id),
                    action="payment.processing.confirmed",
                    ip_address=source_ip,
                    payload={
                        "reservation_id": str(confirmed_payment.reservation_id),
                        "status": confirmed_payment.status.value,
                        "gateway_charge_id": confirmed_payment.gateway_charge_id,
                        "amount_in_cents": confirmed_payment.amount_in_cents,
                        "currency": confirmed_payment.currency,
                        "receipt_number": confirmed_payment.receipt_number,
                    },
                    created_at=confirmed_payment.updated_at,
                )
            )
            self._dispatch_reservation_confirmation_request(
                reservation_id=confirmed_payment.reservation_id,
                payment_id=confirmed_payment.payment_id,
                source_ip=source_ip,
            )
            self._dispatch_notification_request(
                confirmed_payment.payment_id,
                source_ip,
            )
            self.payment_repository.mark_payment_processing_outbox_succeeded(
                outbox_id=item.outbox_id,
                processed_at=confirmed_payment.updated_at,
            )
            return "succeeded"

        if stripe_status in {"requires_payment_method", "canceled"}:
            failure_reason = self._extract_error(intent) or "card_declined"
            failed_payment = apply_gateway_result(
                payment=payment,
                gateway_charge_id=session.payment_intent_id,
                gateway_status=stripe_status,
                status=PaymentStatus.failed,
                failure_reason=failure_reason,
            )
            self.payment_repository.save_payment_result(failed_payment)
            self.payment_repository.add_events(
                failed_payment.payment_id,
                build_terminal_events(failed_payment, session),
            )
            session.status = "failed"
            session.error = failure_reason
            session.updated_at = failed_payment.updated_at
            self.checkout_repository.update_session(session)
            self.audit_repository.add_log(
                PaymentAuditLogRecord(
                    traveler_id=failed_payment.traveler_id,
                    payment_id=failed_payment.payment_id,
                    checkout_session_id=session.payment_transaction_id,
                    entity_type="payment",
                    entity_id=str(failed_payment.payment_id),
                    action="payment.processing.failed",
                    ip_address=source_ip,
                    payload={
                        "reservation_id": str(failed_payment.reservation_id),
                        "status": failed_payment.status.value,
                        "gateway_status": failed_payment.gateway_status,
                        "failure_reason": failed_payment.failure_reason,
                    },
                    created_at=failed_payment.updated_at,
                )
            )
            self.payment_repository.mark_payment_processing_outbox_succeeded(
                outbox_id=item.outbox_id,
                processed_at=failed_payment.updated_at,
            )
            return "succeeded"

        pending_payment = payment.model_copy(
            update={
                "gateway_charge_id": session.payment_intent_id,
                "gateway_status": stripe_status,
                "failure_reason": (
                    self._extract_error(intent)
                    or ("authentication_required" if stripe_status == "requires_action" else None)
                ),
                "updated_at": datetime.now(timezone.utc),
            }
        )
        self.payment_repository.save_payment_result(pending_payment)
        self.payment_repository.add_events(
            pending_payment.payment_id,
            [
                build_intermediate_event(
                    pending_payment,
                    event_type=(
                        "payment.requires_action"
                        if stripe_status == "requires_action"
                        else "payment.processing.awaiting_provider"
                    ),
                    session=session,
                )
            ],
        )
        session.status = stripe_status
        session.error = pending_payment.failure_reason
        session.updated_at = pending_payment.updated_at
        self.checkout_repository.update_session(session)
        self.audit_repository.add_log(
            PaymentAuditLogRecord(
                traveler_id=pending_payment.traveler_id,
                payment_id=pending_payment.payment_id,
                checkout_session_id=session.payment_transaction_id,
                entity_type="payment",
                entity_id=str(pending_payment.payment_id),
                action=(
                    "payment.processing.requires_action"
                    if stripe_status == "requires_action"
                    else "payment.processing.awaiting_provider"
                ),
                ip_address=source_ip,
                payload={
                    "reservation_id": str(pending_payment.reservation_id),
                    "status": pending_payment.status.value,
                    "gateway_status": pending_payment.gateway_status,
                    "failure_reason": pending_payment.failure_reason,
                },
                created_at=pending_payment.updated_at,
            )
        )
        self.payment_repository.mark_payment_processing_outbox_succeeded(
            outbox_id=item.outbox_id,
            processed_at=pending_payment.updated_at,
        )
        return "succeeded"

    def _mark_processing_retry(
        self,
        *,
        item: PaymentProcessingOutboxRecord,
        now: datetime,
        error_message: str,
        source_ip: str | None,
        attempt_count: int | None = None,
    ) -> None:
        next_attempt_count = attempt_count or (item.attempt_count + 1)
        should_fail_terminal = next_attempt_count >= item.max_attempts
        retry_delay_seconds = min(
            settings.payment_processing_retry_max_backoff_seconds,
            settings.payment_processing_retry_base_seconds
            * (2 ** max(0, next_attempt_count - 1)),
        )
        next_retry_at = now + timedelta(seconds=retry_delay_seconds)
        self.payment_repository.mark_payment_processing_outbox_retry(
            outbox_id=item.outbox_id,
            next_retry_at=next_retry_at,
            error_message=error_message,
            attempt_count=next_attempt_count,
            mark_as_failed=should_fail_terminal,
        )
        self.audit_repository.add_log(
            PaymentAuditLogRecord(
                payment_id=item.payment_id,
                checkout_session_id=item.checkout_session_id,
                entity_type="payment",
                entity_id=str(item.payment_id),
                action=(
                    "payment.processing.retry_terminal_failed"
                    if should_fail_terminal
                    else "payment.processing.retry_scheduled"
                ),
                ip_address=source_ip,
                payload={
                    "attempt_count": next_attempt_count,
                    "error": error_message,
                    "next_retry_at": next_retry_at.isoformat(),
                },
                created_at=now,
            )
        )

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

    def _dispatch_notification_request(
        self,
        payment_id: UUID,
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

    def _dispatch_reservation_confirmation_request(
        self,
        reservation_id: UUID,
        payment_id: UUID,
        source_ip: str | None,
    ) -> None:
        try:
            self.reservation_updater.confirm_reservation(
                reservation_id=reservation_id,
                source_ip=source_ip,
            )
            self.audit_repository.add_log(
                PaymentAuditLogRecord(
                    payment_id=payment_id,
                    entity_type="payment",
                    entity_id=str(payment_id),
                    action="reservation.confirmation.requested",
                    ip_address=source_ip,
                    payload={
                        "reservation_id": str(reservation_id),
                        "dispatch_status": "requested",
                    },
                    created_at=datetime.now(timezone.utc),
                )
            )
        except Exception as exc:  # noqa: BLE001
            queued_at = datetime.now(timezone.utc)
            self.payment_repository.upsert_reservation_confirmation_outbox_failure(
                payment_id=payment_id,
                reservation_id=reservation_id,
                error_message=str(exc),
                next_retry_at=queued_at,
                max_attempts=settings.reservation_confirmation_retry_max_attempts,
            )
            self.audit_repository.add_log(
                PaymentAuditLogRecord(
                    payment_id=payment_id,
                    entity_type="payment",
                    entity_id=str(payment_id),
                    action="reservation.confirmation.dispatch_failed",
                    ip_address=source_ip,
                    payload={
                        "reservation_id": str(reservation_id),
                        "error": str(exc),
                        "queued_for_retry": True,
                    },
                    created_at=queued_at,
                )
            )
