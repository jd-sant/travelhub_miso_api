from fastapi import Depends
from sqlmodel import Session

from adapters.gateways.stripe_gateway import FakeStripePaymentGateway, UnsupportedDirectChargeGateway
from adapters.gateways.stripe_checkout_gateway import StripeSdkCheckoutGateway
from adapters.repositories.payment_checkout_repository import SQLModelPaymentCheckoutRepository
from adapters.repositories.payment_audit_repository import SQLModelPaymentAuditRepository
from adapters.repositories.payment_repository import SQLModelPaymentRepository
from adapters.services.notification_dispatcher import (
    HttpNotificationDispatcher,
    NoOpNotificationDispatcher,
)
from core.config import settings
from db.session import get_session
from domain.ports.payment_audit_repository import PaymentAuditRepository
from domain.ports.payment_checkout_repository import PaymentCheckoutRepository
from domain.ports.payment_gateway import PaymentGateway
from domain.ports.notification_dispatcher import NotificationDispatcher
from domain.ports.payment_repository import PaymentRepository
from domain.ports.stripe_checkout_gateway import StripeCheckoutGateway
from domain.use_cases.create_payment_checkout_session import CreatePaymentCheckoutSessionUseCase
from domain.use_cases.create_payment_charge import CreatePaymentChargeUseCase
from domain.use_cases.finalize_stripe_payment import FinalizeStripePaymentUseCase
from domain.use_cases.get_payment_confirmation_summary import GetPaymentConfirmationSummaryUseCase
from domain.use_cases.get_payment import GetPaymentUseCase
from domain.use_cases.get_payment_checkout_session import GetPaymentCheckoutSessionUseCase
from domain.use_cases.handle_stripe_webhook import HandleStripeWebhookUseCase
from domain.use_cases.list_payment_events import ListPaymentEventsUseCase


def get_payment_repository(
    session: Session = Depends(get_session),
) -> PaymentRepository:
    return SQLModelPaymentRepository(session)


def get_payment_checkout_repository(
    session: Session = Depends(get_session),
) -> PaymentCheckoutRepository:
    return SQLModelPaymentCheckoutRepository(session)


def get_payment_audit_repository(
    session: Session = Depends(get_session),
) -> PaymentAuditRepository:
    return SQLModelPaymentAuditRepository(session)


def get_payment_gateway() -> PaymentGateway:
    if settings.payment_provider == "fake_stripe":
        return FakeStripePaymentGateway()
    return UnsupportedDirectChargeGateway(settings.payment_provider)


def get_stripe_checkout_gateway() -> StripeCheckoutGateway:
    return StripeSdkCheckoutGateway()


def get_notification_dispatcher() -> NotificationDispatcher:
    if settings.notifications_service_url:
        return HttpNotificationDispatcher()
    return NoOpNotificationDispatcher()


def get_create_payment_charge_use_case(
    repository: PaymentRepository = Depends(get_payment_repository),
    audit_repository: PaymentAuditRepository = Depends(get_payment_audit_repository),
    gateway: PaymentGateway = Depends(get_payment_gateway),
    notification_dispatcher: NotificationDispatcher = Depends(get_notification_dispatcher),
) -> CreatePaymentChargeUseCase:
    return CreatePaymentChargeUseCase(
        repository,
        audit_repository,
        gateway,
        notification_dispatcher,
    )


def get_get_payment_use_case(
    repository: PaymentRepository = Depends(get_payment_repository),
) -> GetPaymentUseCase:
    return GetPaymentUseCase(repository)


def get_get_payment_confirmation_summary_use_case(
    payment_repository: PaymentRepository = Depends(get_payment_repository),
    checkout_repository: PaymentCheckoutRepository = Depends(get_payment_checkout_repository),
) -> GetPaymentConfirmationSummaryUseCase:
    return GetPaymentConfirmationSummaryUseCase(payment_repository, checkout_repository)


def get_list_payment_events_use_case(
    repository: PaymentRepository = Depends(get_payment_repository),
) -> ListPaymentEventsUseCase:
    return ListPaymentEventsUseCase(repository)


def get_create_payment_checkout_session_use_case(
    repository: PaymentCheckoutRepository = Depends(get_payment_checkout_repository),
    audit_repository: PaymentAuditRepository = Depends(get_payment_audit_repository),
) -> CreatePaymentCheckoutSessionUseCase:
    return CreatePaymentCheckoutSessionUseCase(repository, audit_repository)


def get_finalize_stripe_payment_use_case(
    checkout_repository: PaymentCheckoutRepository = Depends(get_payment_checkout_repository),
    payment_repository: PaymentRepository = Depends(get_payment_repository),
    audit_repository: PaymentAuditRepository = Depends(get_payment_audit_repository),
    gateway: StripeCheckoutGateway = Depends(get_stripe_checkout_gateway),
    notification_dispatcher: NotificationDispatcher = Depends(get_notification_dispatcher),
) -> FinalizeStripePaymentUseCase:
    return FinalizeStripePaymentUseCase(
        checkout_repository,
        payment_repository,
        audit_repository,
        gateway,
        notification_dispatcher,
    )


def get_get_payment_checkout_session_use_case(
    repository: PaymentCheckoutRepository = Depends(get_payment_checkout_repository),
) -> GetPaymentCheckoutSessionUseCase:
    return GetPaymentCheckoutSessionUseCase(repository)


def get_handle_stripe_webhook_use_case(
    checkout_repository: PaymentCheckoutRepository = Depends(get_payment_checkout_repository),
    payment_repository: PaymentRepository = Depends(get_payment_repository),
    audit_repository: PaymentAuditRepository = Depends(get_payment_audit_repository),
    gateway: StripeCheckoutGateway = Depends(get_stripe_checkout_gateway),
    notification_dispatcher: NotificationDispatcher = Depends(get_notification_dispatcher),
) -> HandleStripeWebhookUseCase:
    return HandleStripeWebhookUseCase(
        checkout_repository,
        payment_repository,
        audit_repository,
        gateway,
        notification_dispatcher,
    )
