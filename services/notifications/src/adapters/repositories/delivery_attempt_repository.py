from sqlmodel import Session

from adapters.models.notification_delivery_attempt import NotificationDeliveryAttempt
from domain.ports.delivery_attempt_repository import DeliveryAttemptRepository
from domain.schemas.notification import NotificationDeliveryAttemptRecord


class SQLModelDeliveryAttemptRepository(DeliveryAttemptRepository):
    def __init__(self, session: Session):
        self.session = session

    def add_attempt(self, attempt: NotificationDeliveryAttemptRecord) -> None:
        model = NotificationDeliveryAttempt(
            id=attempt.attempt_id,
            notification_id=attempt.notification_id,
            attempt_number=attempt.attempt_number,
            status=attempt.status.value,
            provider_message_id=attempt.provider_message_id,
            failure_reason=attempt.failure_reason,
            created_at=attempt.created_at,
        )
        self.session.add(model)
        self.session.commit()
