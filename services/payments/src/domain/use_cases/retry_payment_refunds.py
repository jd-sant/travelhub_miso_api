from datetime import datetime, timedelta, timezone
from uuid import uuid4

from core.config import settings
from core.telemetry import refund_latency_seconds, refund_sla_breach_count
from domain.ports.payment_audit_repository import PaymentAuditRepository
from domain.ports.refund_gateway import RefundGateway
from domain.ports.payment_refund_repository import PaymentRefundRepository
from domain.ports.payment_repository import PaymentRepository
from domain.ports.notification_dispatcher import ReservationUpdater
from domain.schemas.audit import PaymentAuditLogRecord
from domain.schemas.payment import PaymentEventResponse, PaymentRefundRetryResponse
from domain.use_cases.base import BaseUseCase


class RetryPaymentRefundsUseCase(BaseUseCase[int, PaymentRefundRetryResponse]):
    def __init__(
        self,
        refund_repository: PaymentRefundRepository,
        payment_repository: PaymentRepository,
        audit_repository: PaymentAuditRepository,
        reservation_updater: ReservationUpdater,
        refund_gateway: RefundGateway,
    ):
        self.refund_repository = refund_repository
        self.payment_repository = payment_repository
        self.audit_repository = audit_repository
        self.reservation_updater = reservation_updater
        self.refund_gateway = refund_gateway

    def execute(
        self,
        payload: int | None = None,
        source_ip: str | None = None,
        correlation_id: str | None = None,
    ) -> PaymentRefundRetryResponse:
        now = datetime.now(timezone.utc)
        limit = payload or settings.refund_retry_batch_size
        refunds = self.refund_repository.list_due_pending_refunds(now=now, limit=limit)

        processed_count = 0
        succeeded_count = 0
        failed_count = 0

        for refund in refunds:
            processed_count += 1
            try:
                self.refund_gateway.process_refund(reason=refund.reason)
                self.refund_repository.mark_refund_succeeded(
                    refund_id=refund.refund_id,
                    processed_at=now,
                )
                self.reservation_updater.notify_refund_result(
                    reservation_id=refund.reservation_id,
                    status="succeeded",
                    amount_in_cents=refund.amount_in_cents,
                    refund_id=refund.refund_id,
                    source_ip=source_ip,
                )
                self.payment_repository.add_events(
                    refund.payment_id,
                    [
                        PaymentEventResponse(
                            event_id=uuid4(),
                            payment_id=refund.payment_id,
                            event_type="payment.refund.succeeded",
                            payload={
                                "refund_id": str(refund.refund_id),
                                "amount_in_cents": refund.amount_in_cents,
                                "currency": refund.currency,
                            },
                            created_at=now,
                        )
                    ],
                )
                self.audit_repository.add_log(
                    PaymentAuditLogRecord(
                        traveler_id=refund.traveler_id,
                        payment_id=refund.payment_id,
                        entity_type="payment_refund",
                        entity_id=str(refund.refund_id),
                        action="payment.refund.retry_succeeded",
                        ip_address=source_ip,
                        payload={
                            "attempt_count": refund.retry_count + 1,
                            "status": "succeeded",
                            "correlation_id": correlation_id,
                        },
                        created_at=now,
                    )
                )
                self.audit_repository.add_log(
                    PaymentAuditLogRecord(
                        traveler_id=refund.traveler_id,
                        payment_id=refund.payment_id,
                        entity_type="payment_refund",
                        entity_id=str(refund.refund_id),
                        action="payment.refund.metrics",
                        ip_address=source_ip,
                        payload={
                            "refund_latency_seconds": refund_latency_seconds(
                                created_at=refund.created_at,
                                now=now,
                            ),
                            "refund_sla_breach_count": refund_sla_breach_count(
                                now=now,
                                sla_deadline_at=refund.sla_deadline_at,
                            ),
                            "correlation_id": correlation_id,
                        },
                        created_at=now,
                    )
                )
                succeeded_count += 1
            except Exception as exc:  # noqa: BLE001
                next_retry_count = refund.retry_count + 1
                should_fail_terminal = next_retry_count >= refund.max_attempts
                retry_delay_seconds = min(
                    settings.refund_retry_max_backoff_seconds,
                    settings.refund_retry_base_seconds
                    * (2 ** max(0, next_retry_count - 1)),
                )
                next_retry_at = now + timedelta(seconds=retry_delay_seconds)

                if should_fail_terminal:
                    try:
                        self.reservation_updater.notify_refund_result(
                            reservation_id=refund.reservation_id,
                            status="failed",
                            amount_in_cents=refund.amount_in_cents,
                            refund_id=refund.refund_id,
                            source_ip=source_ip,
                        )
                    except Exception:
                        # Callback failure should not mask terminal refund failure.
                        pass

                self.refund_repository.mark_refund_retry(
                    refund_id=refund.refund_id,
                    next_retry_at=next_retry_at,
                    error_message=str(exc),
                    retry_count=next_retry_count,
                    mark_as_failed=should_fail_terminal,
                )
                self.payment_repository.add_events(
                    refund.payment_id,
                    [
                        PaymentEventResponse(
                            event_id=uuid4(),
                            payment_id=refund.payment_id,
                            event_type=(
                                "payment.refund.failed"
                                if should_fail_terminal
                                else "payment.refund.retry_failed"
                            ),
                            payload={
                                "refund_id": str(refund.refund_id),
                                "attempt_count": next_retry_count,
                                "error": str(exc),
                                "next_retry_at": next_retry_at.isoformat(),
                            },
                            created_at=now,
                        )
                    ],
                )
                self.audit_repository.add_log(
                    PaymentAuditLogRecord(
                        traveler_id=refund.traveler_id,
                        payment_id=refund.payment_id,
                        entity_type="payment_refund",
                        entity_id=str(refund.refund_id),
                        action=(
                            "payment.refund.retry_terminal_failed"
                            if should_fail_terminal
                            else "payment.refund.retry_failed"
                        ),
                        ip_address=source_ip,
                        payload={
                            "attempt_count": next_retry_count,
                            "error": str(exc),
                            "next_retry_at": next_retry_at.isoformat(),
                            "correlation_id": correlation_id,
                        },
                        created_at=now,
                    )
                )
                self.audit_repository.add_log(
                    PaymentAuditLogRecord(
                        traveler_id=refund.traveler_id,
                        payment_id=refund.payment_id,
                        entity_type="payment_refund",
                        entity_id=str(refund.refund_id),
                        action="payment.refund.metrics",
                        ip_address=source_ip,
                        payload={
                            "refund_latency_seconds": refund_latency_seconds(
                                created_at=refund.created_at,
                                now=now,
                            ),
                            "refund_sla_breach_count": refund_sla_breach_count(
                                now=now,
                                sla_deadline_at=refund.sla_deadline_at,
                            ),
                            "correlation_id": correlation_id,
                        },
                        created_at=now,
                    )
                )
                failed_count += 1

        pending_count = self.refund_repository.count_pending_refunds(now=now)
        return PaymentRefundRetryResponse(
            processed_count=processed_count,
            succeeded_count=succeeded_count,
            failed_count=failed_count,
            pending_count=pending_count,
        )
