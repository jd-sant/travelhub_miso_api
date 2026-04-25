from fastapi import Depends
from sqlmodel import Session

from adapters.repositories.delivery_attempt_repository import SQLModelDeliveryAttemptRepository
from adapters.repositories.notification_audit_repository import SQLModelNotificationAuditRepository
from adapters.repositories.notification_repository import SQLModelNotificationRepository
from adapters.services.in_process_notification_delivery_runner import (
    InProcessNotificationDeliveryRunner,
)
from adapters.services.log_email_sender import LogEmailSender
from adapters.services.payment_confirmation_client import HttpPaymentConfirmationClient
from core.config import settings
from db.session import engine, get_session
from domain.ports.delivery_attempt_repository import DeliveryAttemptRepository
from domain.ports.email_sender import EmailSender
from domain.ports.notification_audit_repository import NotificationAuditRepository
from domain.ports.notification_delivery_runner import NotificationDeliveryRunner
from domain.ports.notification_repository import NotificationRepository
from domain.ports.payment_confirmation_source import PaymentConfirmationSource
from domain.ports.traveler_profile_source import TravelerProfileSource
from domain.use_cases.create_payment_confirmation import CreatePaymentConfirmationUseCase
from domain.use_cases.create_reservation_update import CreateReservationUpdateUseCase
from domain.use_cases.get_notification import GetNotificationUseCase
from domain.use_cases.send_payment_confirmation import SendPaymentConfirmationUseCase
from errors import PaymentConfirmationUnavailableError


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
    if settings.ses_from_address:
        from adapters.services.ses_email_sender import SesEmailSender

        return SesEmailSender()
    if settings.smtp_host:
        from adapters.services.smtp_email_sender import SmtpEmailSender

        return SmtpEmailSender()
    if settings.app_env not in ("development", "dev", "test"):
        raise PaymentConfirmationUnavailableError(
            "SES_FROM_ADDRESS o SMTP_HOST debe estar configurado para despachar confirmaciones en entornos no-dev."
        )
    return LogEmailSender()


def get_payment_confirmation_source() -> PaymentConfirmationSource:
    return HttpPaymentConfirmationClient()


def get_traveler_profile_source() -> TravelerProfileSource:
    from adapters.services.traveler_profile_client import HttpTravelerProfileClient

    return HttpTravelerProfileClient()


def get_create_payment_confirmation_use_case(
    notification_repository: NotificationRepository = Depends(get_notification_repository),
    audit_repository: NotificationAuditRepository = Depends(get_notification_audit_repository),
    payment_confirmation_source: PaymentConfirmationSource = Depends(get_payment_confirmation_source),
    traveler_profile_source: TravelerProfileSource = Depends(get_traveler_profile_source),
) -> CreatePaymentConfirmationUseCase:
    return CreatePaymentConfirmationUseCase(
        notification_repository,
        audit_repository,
        payment_confirmation_source,
        traveler_profile_source,
    )


def get_create_reservation_update_use_case(
    notification_repository: NotificationRepository = Depends(get_notification_repository),
    audit_repository: NotificationAuditRepository = Depends(get_notification_audit_repository),
    traveler_profile_source: TravelerProfileSource = Depends(get_traveler_profile_source),
) -> CreateReservationUpdateUseCase:
    return CreateReservationUpdateUseCase(
        notification_repository,
        audit_repository,
        traveler_profile_source,
    )


def get_send_payment_confirmation_use_case(
    notification_repository: NotificationRepository = Depends(get_notification_repository),
    delivery_attempt_repository: DeliveryAttemptRepository = Depends(get_delivery_attempt_repository),
    audit_repository: NotificationAuditRepository = Depends(get_notification_audit_repository),
    email_sender: EmailSender = Depends(get_email_sender),
) -> SendPaymentConfirmationUseCase:
    return SendPaymentConfirmationUseCase(
        notification_repository,
        delivery_attempt_repository,
        audit_repository,
        email_sender,
    )


def get_get_notification_use_case(
    repository: NotificationRepository = Depends(get_notification_repository),
) -> GetNotificationUseCase:
    return GetNotificationUseCase(repository)


def get_notification_delivery_runner(
    email_sender: EmailSender = Depends(get_email_sender),
) -> NotificationDeliveryRunner:
    return InProcessNotificationDeliveryRunner(
        session_factory=lambda: Session(engine),
        email_sender=email_sender,
    )
