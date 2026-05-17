from datetime import datetime, timezone
from uuid import uuid4

from core.config import settings
from core.security import (
    build_duplicate_guard_key,
    build_payment_fingerprint,
    build_request_checksum,
    hash_token,
)
from domain.schemas.checkout import PaymentCheckoutSessionRecord
from domain.schemas.payment import PaymentChargeResponse, PaymentEventResponse, PaymentStatus


def build_pending_payment(
    *,
    session: PaymentCheckoutSessionRecord,
    confirmation_token_id: str,
) -> PaymentChargeResponse:
    now = datetime.now(timezone.utc)
    token_hash = hash_token(confirmation_token_id)
    request_fingerprint = build_payment_fingerprint(
        reservation_id=str(session.reservation_id),
        traveler_id=str(session.traveler_id),
        amount_in_cents=session.amount_in_cents,
        currency=session.currency,
        token_hash=token_hash,
    )
    duplicate_guard_key = build_duplicate_guard_key(
        request_fingerprint=request_fingerprint,
        bucket=int(now.timestamp() // settings.payment_duplicate_window_seconds),
    )
    request_checksum = build_request_checksum(
        "|".join(
            [
                str(session.reservation_id),
                str(session.traveler_id),
                str(session.amount_in_cents),
                session.currency,
                confirmation_token_id,
                session.idempotency_key,
            ]
        ),
        settings.payment_integrity_secret,
    )
    return PaymentChargeResponse(
        payment_id=uuid4(),
        reservation_id=session.reservation_id,
        traveler_id=session.traveler_id,
        provider_code=session.provider_code,
        status=PaymentStatus.pending,
        amount_in_cents=session.amount_in_cents,
        currency=session.currency,
        gateway_charge_id=None,
        gateway_status="queued",
        idempotency_key=session.idempotency_key,
        request_fingerprint=request_fingerprint,
        duplicate_guard_key=duplicate_guard_key,
        request_checksum=request_checksum,
        payment_method_token_hash=token_hash,
        failure_reason=None,
        card_brand=None,
        card_last4=None,
        created_at=now,
        updated_at=now,
    )


def apply_gateway_result(
    *,
    payment: PaymentChargeResponse,
    gateway_charge_id: str | None,
    gateway_status: str,
    status: PaymentStatus,
    failure_reason: str | None,
) -> PaymentChargeResponse:
    now = datetime.now(timezone.utc)
    updated = payment.model_copy(
        update={
            "status": status,
            "gateway_charge_id": gateway_charge_id,
            "gateway_status": gateway_status,
            "failure_reason": failure_reason,
            "card_brand": "visa" if status == PaymentStatus.confirmed else None,
            "card_last4": "4242" if status == PaymentStatus.confirmed else None,
            "updated_at": now,
        }
    )
    if status == PaymentStatus.confirmed and updated.receipt_id is None:
        updated.receipt_id = uuid4()
        updated.receipt_number = now.strftime("RCPT-%Y%m%d-%H%M%S")
    if status != PaymentStatus.confirmed:
        updated.receipt_id = None
        updated.receipt_number = None
    return updated


def build_pending_events(
    payment: PaymentChargeResponse,
    session: PaymentCheckoutSessionRecord | None = None,
) -> list[PaymentEventResponse]:
    now = datetime.now(timezone.utc)
    payload = _build_base_payload(payment, session)
    return [
        PaymentEventResponse(
            event_id=uuid4(),
            payment_id=payment.payment_id,
            event_type="payment.pending",
            payload=payload,
            created_at=now,
        ),
        PaymentEventResponse(
            event_id=uuid4(),
            payment_id=payment.payment_id,
            event_type="payment.processing.requested",
            payload=payload,
            created_at=now,
        ),
    ]


def build_processing_started_event(
    payment: PaymentChargeResponse,
    session: PaymentCheckoutSessionRecord | None = None,
) -> PaymentEventResponse:
    return PaymentEventResponse(
        event_id=uuid4(),
        payment_id=payment.payment_id,
        event_type="payment.processing.started",
        payload=_build_base_payload(payment, session),
        created_at=datetime.now(timezone.utc),
    )


def build_terminal_events(
    payment: PaymentChargeResponse,
    session: PaymentCheckoutSessionRecord | None = None,
) -> list[PaymentEventResponse]:
    now = datetime.now(timezone.utc)
    payload = _build_base_payload(payment, session)
    event_types = (
        [
            "payment.succeeded",
            "reservation.confirmation.requested",
            "notification.payment_confirmation.requested",
            "inventory.update.requested",
            "receipt.generated",
        ]
        if payment.status == PaymentStatus.confirmed
        else ["payment.failed"]
    )
    return [
        PaymentEventResponse(
            event_id=uuid4(),
            payment_id=payment.payment_id,
            event_type=event_type,
            payload=payload,
            created_at=now,
        )
        for event_type in event_types
    ]


def build_intermediate_event(
    payment: PaymentChargeResponse,
    *,
    event_type: str,
    session: PaymentCheckoutSessionRecord | None = None,
) -> PaymentEventResponse:
    return PaymentEventResponse(
        event_id=uuid4(),
        payment_id=payment.payment_id,
        event_type=event_type,
        payload=_build_base_payload(payment, session),
        created_at=datetime.now(timezone.utc),
    )


def _build_base_payload(
    payment: PaymentChargeResponse,
    session: PaymentCheckoutSessionRecord | None = None,
) -> dict:
    return {
        "payment_id": str(payment.payment_id),
        "reservation_id": str(payment.reservation_id),
        "traveler_id": str(payment.traveler_id),
        "amount_in_cents": payment.amount_in_cents,
        "currency": payment.currency,
        "gateway_charge_id": payment.gateway_charge_id,
        "receipt_id": str(payment.receipt_id) if payment.receipt_id else None,
        "receipt_number": payment.receipt_number,
        "status": payment.status.value,
        "gateway_status": payment.gateway_status,
        "failure_reason": payment.failure_reason,
        "property_name": session.property_name if session else None,
        "check_in_date": (
            session.check_in_date.isoformat()
            if session and session.check_in_date
            else None
        ),
        "check_out_date": (
            session.check_out_date.isoformat()
            if session and session.check_out_date
            else None
        ),
    }
