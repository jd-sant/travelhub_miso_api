from collections.abc import Callable
from uuid import UUID

from sqlmodel import Session

from adapters.repositories.delivery_attempt_repository import SQLModelDeliveryAttemptRepository
from adapters.repositories.notification_audit_repository import SQLModelNotificationAuditRepository
from adapters.repositories.notification_repository import SQLModelNotificationRepository
from domain.ports.email_sender import EmailSender
from domain.ports.notification_delivery_runner import NotificationDeliveryRunner
from domain.use_cases.send_payment_confirmation import SendPaymentConfirmationUseCase


class InProcessNotificationDeliveryRunner(NotificationDeliveryRunner):
    def __init__(
        self,
        session_factory: Callable[[], Session],
        email_sender: EmailSender,
    ):
        self.session_factory = session_factory
        self.email_sender = email_sender

    def run_delivery(
        self,
        *,
        notification_id: UUID,
        source_ip: str | None = None,
    ) -> None:
        with self.session_factory() as session:
            use_case = SendPaymentConfirmationUseCase(
                notification_repository=SQLModelNotificationRepository(session),
                delivery_attempt_repository=SQLModelDeliveryAttemptRepository(session),
                audit_repository=SQLModelNotificationAuditRepository(session),
                email_sender=self.email_sender,
            )
            use_case.execute(notification_id, source_ip)
