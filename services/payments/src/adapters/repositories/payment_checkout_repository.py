from uuid import UUID

from sqlmodel import Session, select

from adapters.models.payment_checkout_session import PaymentCheckoutSession
from core.config import settings
from core.security import decrypt_sensitive_value, encrypt_sensitive_value
from domain.ports.payment_checkout_repository import PaymentCheckoutRepository
from domain.schemas.checkout import PaymentCheckoutSessionRecord


def _to_record(model: PaymentCheckoutSession) -> PaymentCheckoutSessionRecord:
    return PaymentCheckoutSessionRecord(
        payment_transaction_id=model.id,
        reservation_id=model.reservation_id,
        traveler_id=model.traveler_id,
        provider_code=model.provider_code,
        amount_in_cents=model.amount_in_cents,
        currency=model.currency,
        property_name=model.property_name,
        check_in_date=model.check_in_date,
        check_out_date=model.check_out_date,
        idempotency_key=model.idempotency_key,
        confirmation_token_id=decrypt_sensitive_value(
            model.confirmation_token_id,
            settings.payments_data_encryption_key,
        ),
        payment_intent_id=model.stripe_payment_intent_id,
        status=model.status,
        payment_id=model.payment_id,
        client_secret=decrypt_sensitive_value(
            model.client_secret,
            settings.payments_data_encryption_key,
        ),
        error=model.last_error_message,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


class SQLModelPaymentCheckoutRepository(PaymentCheckoutRepository):
    def __init__(self, session: Session):
        self.session = session

    def create_session(self, session: PaymentCheckoutSessionRecord) -> PaymentCheckoutSessionRecord:
        model = PaymentCheckoutSession(
            id=session.payment_transaction_id,
            reservation_id=session.reservation_id,
            traveler_id=session.traveler_id,
            provider_code=session.provider_code,
            amount_in_cents=session.amount_in_cents,
            currency=session.currency,
            property_name=session.property_name,
            check_in_date=session.check_in_date,
            check_out_date=session.check_out_date,
            idempotency_key=session.idempotency_key,
            confirmation_token_id=encrypt_sensitive_value(
                session.confirmation_token_id,
                settings.payments_data_encryption_key,
            ),
            stripe_payment_intent_id=session.payment_intent_id,
            status=session.status,
            payment_id=session.payment_id,
            client_secret=encrypt_sensitive_value(
                session.client_secret,
                settings.payments_data_encryption_key,
            ),
            last_error_message=session.error,
            created_at=session.created_at,
            updated_at=session.updated_at,
        )
        self.session.add(model)
        self.session.commit()
        self.session.refresh(model)
        return _to_record(model)

    def get_session(self, payment_transaction_id: UUID) -> PaymentCheckoutSessionRecord | None:
        model = self.session.get(PaymentCheckoutSession, payment_transaction_id)
        return _to_record(model) if model else None

    def get_session_by_payment_intent(self, payment_intent_id: str) -> PaymentCheckoutSessionRecord | None:
        model = self.session.exec(
            select(PaymentCheckoutSession).where(
                PaymentCheckoutSession.stripe_payment_intent_id == payment_intent_id
            )
        ).first()
        return _to_record(model) if model else None

    def get_session_by_payment_id(self, payment_id: UUID) -> PaymentCheckoutSessionRecord | None:
        model = self.session.exec(
            select(PaymentCheckoutSession).where(
                PaymentCheckoutSession.payment_id == payment_id
            )
        ).first()
        return _to_record(model) if model else None

    def update_session(self, session: PaymentCheckoutSessionRecord) -> PaymentCheckoutSessionRecord:
        model = self.session.get(PaymentCheckoutSession, session.payment_transaction_id)
        if model is None:
            raise ValueError("Payment checkout session not found")

        model.confirmation_token_id = encrypt_sensitive_value(
            session.confirmation_token_id,
            settings.payments_data_encryption_key,
        )
        model.stripe_payment_intent_id = session.payment_intent_id
        model.status = session.status
        model.payment_id = session.payment_id
        model.client_secret = encrypt_sensitive_value(
            session.client_secret,
            settings.payments_data_encryption_key,
        )
        model.last_error_message = session.error
        model.updated_at = session.updated_at

        self.session.add(model)
        self.session.commit()
        self.session.refresh(model)
        return _to_record(model)
