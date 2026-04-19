from uuid import UUID

import httpx

from core.config import settings
from domain.ports.payment_service_client import PaymentServiceClient
from errors import PaymentServiceUnavailableError


class HttpPaymentServiceClient(PaymentServiceClient):
    def request_refund(
        self,
        *,
        reservation_id: UUID,
        amount_in_cents: int,
        reason: str,
        idempotency_key: str,
        source_ip: str | None = None,
    ) -> None:
        url = f"{settings.payments_service_url}/api/v1/internal/payments/refunds"
        try:
            response = httpx.post(
                url,
                json={
                    "reservation_id": str(reservation_id),
                    "amount_in_cents": amount_in_cents,
                    "reason": reason,
                    "idempotency_key": idempotency_key,
                },
                headers={"X-Internal-Api-Key": settings.internal_api_key},
                timeout=5.0,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise PaymentServiceUnavailableError(
                "No se pudo iniciar el flujo de reembolso en payments"
            ) from exc

    def request_additional_charge(
        self,
        *,
        reservation_id: UUID,
        traveler_id: UUID,
        amount_in_cents: int,
        currency: str,
        idempotency_key: str,
        source_ip: str | None = None,
    ) -> None:
        url = f"{settings.payments_service_url}/api/v1/internal/payments/additional-charges"
        try:
            response = httpx.post(
                url,
                json={
                    "reservation_id": str(reservation_id),
                    "traveler_id": str(traveler_id),
                    "amount_in_cents": amount_in_cents,
                    "currency": currency,
                    "idempotency_key": idempotency_key,
                },
                headers={"X-Internal-Api-Key": settings.internal_api_key},
                timeout=5.0,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise PaymentServiceUnavailableError(
                "No se pudo iniciar el cobro adicional en payments"
            ) from exc
