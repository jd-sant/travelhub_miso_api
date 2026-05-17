from uuid import UUID

import httpx

from core.config import settings
from domain.ports.payment_event_source import PaymentEventSource
from domain.schemas.notification import PaymentPublicSourceRecord, RefundPublicSourceRecord
from errors import PaymentConfirmationUnavailableError


class HttpPaymentEventClient(PaymentEventSource):
    def get_payment(self, payment_id: UUID) -> PaymentPublicSourceRecord:
        url = f"{settings.payments_service_url}/api/v1/payments/{payment_id}"
        try:
            response = httpx.get(url, timeout=5.0)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise PaymentConfirmationUnavailableError(
                "No fue posible consultar el estado del pago."
            ) from exc

        payload = response.json()
        return PaymentPublicSourceRecord(
            payment_id=payload["payment_id"],
            reservation_id=payload["reservation_id"],
            status=payload["status"],
            amount_in_cents=payload["amount_in_cents"],
            currency=payload["currency"],
            receipt_number=payload.get("receipt_number"),
        )

    def get_refund(self, refund_id: UUID) -> RefundPublicSourceRecord:
        url = f"{settings.payments_service_url}/api/v1/payments/refunds/{refund_id}"
        try:
            response = httpx.get(url, timeout=5.0)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise PaymentConfirmationUnavailableError(
                "No fue posible consultar el estado del reembolso."
            ) from exc

        payload = response.json()
        return RefundPublicSourceRecord(
            refund_id=payload["refund_id"],
            payment_id=payload["payment_id"],
            reservation_id=payload["reservation_id"],
            status=payload["status"],
            amount_in_cents=payload["amount_in_cents"],
            currency=payload["currency"],
            reason=payload["reason"],
        )
