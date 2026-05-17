from fastapi import Depends
from sqlmodel import Session

from adapters.repositories.delivery_attempt_repository import SQLModelDeliveryAttemptRepository
from adapters.repositories.device_token_repository import SQLModelDeviceTokenRepository
from adapters.repositories.notification_audit_repository import SQLModelNotificationAuditRepository
from adapters.repositories.notification_preference_repository import (
    SQLModelNotificationPreferenceRepository,
)
from adapters.repositories.notification_repository import SQLModelNotificationRepository
from adapters.services.in_process_notification_delivery_runner import (
    InProcessNotificationDeliveryRunner,
)
from adapters.services.log_email_sender import LogEmailSender
from adapters.services.payment_confirmation_client import HttpPaymentConfirmationClient
from adapters.services.payment_event_client import HttpPaymentEventClient
from core.config import settings
from db.session import engine, get_session
from domain.ports.delivery_attempt_repository import DeliveryAttemptRepository
from domain.ports.device_token_repository import DeviceTokenRepository
from domain.ports.email_sender import EmailSender
from domain.ports.notification_audit_repository import NotificationAuditRepository
from domain.ports.notification_delivery_runner import NotificationDeliveryRunner
from domain.ports.notification_preference_repository import (
    NotificationPreferenceRepository,
)
from domain.ports.notification_repository import NotificationRepository
from domain.ports.payment_confirmation_source import PaymentConfirmationSource
from domain.ports.payment_event_source import PaymentEventSource
from domain.ports.push_sender import PushSender
from domain.ports.traveler_profile_source import TravelerProfileSource
from domain.services.push_notifier import PushNotifier
from domain.use_cases.create_reservation_event_notification import (
    CreateReservationEventNotificationUseCase,
)
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


def get_payment_event_source() -> PaymentEventSource:
    return HttpPaymentEventClient()


def get_device_token_repository(
    session: Session = Depends(get_session),
) -> DeviceTokenRepository:
    return SQLModelDeviceTokenRepository(session)


def get_notification_preference_repository(
    session: Session = Depends(get_session),
) -> NotificationPreferenceRepository:
    return SQLModelNotificationPreferenceRepository(session)


def get_push_sender() -> PushSender:
    if settings.fcm_project_id and settings.fcm_service_account_json:
        from adapters.services.fcm_push_sender import FcmPushSender

        return FcmPushSender()
    from adapters.services.log_push_sender import LogPushSender

    return LogPushSender()


def get_push_notifier(
    device_token_repository: DeviceTokenRepository = Depends(get_device_token_repository),
    preference_repository: NotificationPreferenceRepository = Depends(
        get_notification_preference_repository
    ),
    push_sender: PushSender = Depends(get_push_sender),
    audit_repository: NotificationAuditRepository = Depends(get_notification_audit_repository),
) -> PushNotifier:
    return PushNotifier(
        device_token_repository=device_token_repository,
        preference_repository=preference_repository,
        push_sender=push_sender,
        audit_repository=audit_repository,
    )


def get_create_payment_confirmation_use_case(
    notification_repository: NotificationRepository = Depends(get_notification_repository),
    audit_repository: NotificationAuditRepository = Depends(get_notification_audit_repository),
    payment_confirmation_source: PaymentConfirmationSource = Depends(get_payment_confirmation_source),
    traveler_profile_source: TravelerProfileSource = Depends(get_traveler_profile_source),
    push_notifier: PushNotifier = Depends(get_push_notifier),
) -> CreatePaymentConfirmationUseCase:
    return CreatePaymentConfirmationUseCase(
        notification_repository,
        audit_repository,
        payment_confirmation_source,
        traveler_profile_source,
        push_notifier=push_notifier,
    )


def get_create_reservation_update_use_case(
    notification_repository: NotificationRepository = Depends(get_notification_repository),
    audit_repository: NotificationAuditRepository = Depends(get_notification_audit_repository),
    traveler_profile_source: TravelerProfileSource = Depends(get_traveler_profile_source),
    push_notifier: PushNotifier = Depends(get_push_notifier),
) -> CreateReservationUpdateUseCase:
    return CreateReservationUpdateUseCase(
        notification_repository,
        audit_repository,
        traveler_profile_source,
        push_notifier=push_notifier,
    )


def get_create_reservation_event_notification_use_case(
    notification_repository: NotificationRepository = Depends(get_notification_repository),
    audit_repository: NotificationAuditRepository = Depends(get_notification_audit_repository),
    traveler_profile_source: TravelerProfileSource = Depends(get_traveler_profile_source),
    payment_event_source: PaymentEventSource = Depends(get_payment_event_source),
    device_token_repository: DeviceTokenRepository = Depends(get_device_token_repository),
    preference_repository: NotificationPreferenceRepository = Depends(
        get_notification_preference_repository
    ),
    push_sender: PushSender = Depends(get_push_sender),
) -> CreateReservationEventNotificationUseCase:
    return CreateReservationEventNotificationUseCase(
        notification_repository,
        audit_repository,
        traveler_profile_source,
        payment_event_source,
        device_token_repository=device_token_repository,
        preference_repository=preference_repository,
        push_sender=push_sender,
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
