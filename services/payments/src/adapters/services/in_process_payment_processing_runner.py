from collections.abc import Callable
from uuid import UUID

from sqlmodel import Session

from adapters.repositories.payment_audit_repository import SQLModelPaymentAuditRepository
from adapters.repositories.payment_checkout_repository import (
    SQLModelPaymentCheckoutRepository,
)
from adapters.repositories.payment_repository import SQLModelPaymentRepository
from domain.ports.notification_dispatcher import (
    NotificationDispatcher,
    ReservationUpdater,
)
from domain.ports.payment_processing_runner import PaymentProcessingRunner
from domain.ports.stripe_checkout_gateway import StripeCheckoutGateway
from domain.use_cases.process_queued_payments import ProcessQueuedPaymentsUseCase


class InProcessPaymentProcessingRunner(PaymentProcessingRunner):
    def __init__(
        self,
        *,
        session_factory: Callable[[], Session],
        gateway: StripeCheckoutGateway,
        notification_dispatcher: NotificationDispatcher,
        reservation_updater: ReservationUpdater,
    ):
        self.session_factory = session_factory
        self.gateway = gateway
        self.notification_dispatcher = notification_dispatcher
        self.reservation_updater = reservation_updater

    def run_checkout_processing(
        self,
        *,
        payment_transaction_id: UUID,
        source_ip: str | None = None,
    ) -> None:
        with self.session_factory() as session:
            use_case = ProcessQueuedPaymentsUseCase(
                payment_repository=SQLModelPaymentRepository(session),
                checkout_repository=SQLModelPaymentCheckoutRepository(session),
                audit_repository=SQLModelPaymentAuditRepository(session),
                gateway=self.gateway,
                notification_dispatcher=self.notification_dispatcher,
                reservation_updater=self.reservation_updater,
            )
            use_case.execute(payment_transaction_id, source_ip=source_ip)
