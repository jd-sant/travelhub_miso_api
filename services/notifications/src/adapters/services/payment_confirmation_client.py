from uuid import UUID

import httpx

from core.config import settings
from domain.ports.payment_confirmation_source import PaymentConfirmationSource
from domain.schemas.notification import PaymentConfirmationSourceRecord
from errors import InvalidPaymentConfirmationError, PaymentConfirmationUnavailableError


class HttpPaymentConfirmationClient(PaymentConfirmationSource):
    def get_confirmation(self, payment_id: UUID) -> PaymentConfirmationSourceRecord:
        url = f"{settings.payments_service_url}/api/v1/payments/{payment_id}/confirmation"
        try:
            response = httpx.get(url, timeout=5.0)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                raise InvalidPaymentConfirmationError(
                    f"El pago {payment_id} no existe o no tiene resumen de confirmacion."
                ) from exc
            raise PaymentConfirmationUnavailableError(
                "No fue posible consultar el resumen de confirmacion del pago."
            ) from exc
        except httpx.HTTPError as exc:
            raise PaymentConfirmationUnavailableError(
                "No fue posible consultar el resumen de confirmacion del pago."
            ) from exc

        payload = response.json()
        return PaymentConfirmationSourceRecord(
            payment_id=payload["payment_id"],
            reservation_id=payload["reservation_id"],
            traveler_id=payload["traveler_id"],
            status=payload["status"],
            amount_in_cents=payload["amount_in_cents"],
            currency=payload["currency"],
            receipt_id=payload.get("receipt_id"),
            receipt_number=payload.get("receipt_number"),
            property_name=payload.get("property_name"),
            check_in_date=payload.get("check_in_date"),
            check_out_date=payload.get("check_out_date"),
        )
