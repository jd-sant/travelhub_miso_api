from fastapi import Depends
from sqlmodel import Session

from adapters.repositories.delivery_attempt_repository import SQLModelDeliveryAttemptRepository
from adapters.repositories.notification_audit_repository import SQLModelNotificationAuditRepository
from adapters.repositories.notification_repository import SQLModelNotificationRepository
from adapters.services.log_email_sender import LogEmailSender
from core.config import settings
from db.session import get_session
from domain.ports.delivery_attempt_repository import DeliveryAttemptRepository
from domain.ports.email_sender import EmailSender
from domain.ports.notification_audit_repository import NotificationAuditRepository
from domain.ports.notification_repository import NotificationRepository
from domain.use_cases.create_payment_confirmation import CreatePaymentConfirmationUseCase
from domain.use_cases.get_notification import GetNotificationUseCase


def get_notification_repository(session: Session = Depends(get_session)) -> NotificationRepository:
    return SQLModelNotificationRepository(session)


def get_delivery_attempt_repository(
    session: Session = Depends(get_session),
) -> DeliveryAttemptRepository:
    return SQLModelDeliveryAttemptRepository(session)


def get_notification_audit_repository(
    session: Session = Depends(get_session),
) -> NotificationAuditRepository:
    return SQLModelNotificationAuditRepository(session)


def get_email_sender() -> EmailSender:
    if settings.smtp_host:
        from adapters.services.smtp_email_sender import SmtpEmailSender

        return SmtpEmailSender()
    return LogEmailSender()


def get_create_payment_confirmation_use_case(
    notification_repository: NotificationRepository = Depends(get_notification_repository),
    delivery_attempt_repository: DeliveryAttemptRepository = Depends(get_delivery_attempt_repository),
    audit_repository: NotificationAuditRepository = Depends(get_notification_audit_repository),
    email_sender: EmailSender = Depends(get_email_sender),
) -> CreatePaymentConfirmationUseCase:
    return CreatePaymentConfirmationUseCase(
        notification_repository,
        delivery_attempt_repository,
        audit_repository,
        email_sender,
    )


def get_get_notification_use_case(
    repository: NotificationRepository = Depends(get_notification_repository),
) -> GetNotificationUseCase:
    return GetNotificationUseCase(repository)
