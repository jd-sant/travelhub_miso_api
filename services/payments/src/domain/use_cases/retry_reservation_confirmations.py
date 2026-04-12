from datetime import datetime, timedelta, timezone

from core.config import settings
from domain.ports.notification_dispatcher import ReservationUpdater
from domain.ports.payment_audit_repository import PaymentAuditRepository
from domain.ports.payment_repository import PaymentRepository
from domain.schemas.audit import PaymentAuditLogRecord
from domain.schemas.payment import ReservationConfirmationRetryResponse
from domain.use_cases.base import BaseUseCase


class RetryReservationConfirmationsUseCase(BaseUseCase[int, ReservationConfirmationRetryResponse]):
    def __init__(
        self,
        repository: PaymentRepository,
        audit_repository: PaymentAuditRepository,
        reservation_updater: ReservationUpdater,
    ):
        self.repository = repository
        self.audit_repository = audit_repository
        self.reservation_updater = reservation_updater

    def execute(
        self,
        payload: int | None = None,
        source_ip: str | None = None,
    ) -> ReservationConfirmationRetryResponse:
        now = datetime.now(timezone.utc)
        limit = payload or settings.reservation_confirmation_retry_batch_size
        items = self.repository.list_due_reservation_confirmation_outbox(now=now, limit=limit)

        processed_count = 0
        succeeded_count = 0
        failed_count = 0

        for item in items:
            processed_count += 1
            try:
                self.reservation_updater.confirm_reservation(
                    reservation_id=item.reservation_id,
                    source_ip=source_ip,
                )
                succeeded_count += 1
                self.repository.mark_reservation_confirmation_outbox_succeeded(
                    outbox_id=item.outbox_id,
                    processed_at=now,
                )
                self.audit_repository.add_log(
                    PaymentAuditLogRecord(
                        payment_id=item.payment_id,
                        entity_type="payment",
                        entity_id=str(item.payment_id),
                        action="reservation.confirmation.retry_succeeded",
                        ip_address=source_ip,
                        payload={
                            "reservation_id": str(item.reservation_id),
                            "attempt_count": item.attempt_count,
                        },
                        created_at=now,
                    )
                )
            except Exception as exc:  # noqa: BLE001
                failed_count += 1
                next_attempt_count = item.attempt_count + 1
                should_fail_terminal = next_attempt_count >= item.max_attempts
                retry_delay_seconds = min(
                    settings.reservation_confirmation_retry_max_backoff_seconds,
                    settings.reservation_confirmation_retry_base_seconds
                    * (2 ** max(0, next_attempt_count - 2)),
                )
                next_retry_at = now + timedelta(seconds=retry_delay_seconds)
                self.repository.mark_reservation_confirmation_outbox_retry(
                    outbox_id=item.outbox_id,
                    next_retry_at=next_retry_at,
                    error_message=str(exc),
                    attempt_count=next_attempt_count,
                    mark_as_failed=should_fail_terminal,
                )
                self.audit_repository.add_log(
                    PaymentAuditLogRecord(
                        payment_id=item.payment_id,
                        entity_type="payment",
                        entity_id=str(item.payment_id),
                        action=(
                            "reservation.confirmation.retry_terminal_failed"
                            if should_fail_terminal
                            else "reservation.confirmation.retry_failed"
                        ),
                        ip_address=source_ip,
                        payload={
                            "reservation_id": str(item.reservation_id),
                            "attempt_count": next_attempt_count,
                            "error": str(exc),
                            "next_retry_at": next_retry_at.isoformat(),
                        },
                        created_at=now,
                    )
                )

        pending_count = self.repository.count_reservation_confirmation_outbox_pending(now=now)
        return ReservationConfirmationRetryResponse(
            processed_count=processed_count,
            succeeded_count=succeeded_count,
            failed_count=failed_count,
            pending_count=pending_count,
        )
