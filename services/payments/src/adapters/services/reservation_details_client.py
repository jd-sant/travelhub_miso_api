"""Cliente HTTP best-effort para obtener detalles de reserva/propiedad.

Se usa al construir la confirmación de pago para enriquecer el payload con
número de huéspedes y dirección de la propiedad. Cualquier fallo retorna None;
el correo sigue enviándose con los datos disponibles (la HU no requiere estos
campos como bloqueantes, pero sí mejorar la experiencia del viajero).
"""

from __future__ import annotations

import logging
from uuid import UUID

import httpx

from core.config import settings

logger = logging.getLogger(__name__)


class ReservationDetailsClient:
    def fetch_guests_and_property(
        self,
        reservation_id: UUID,
    ) -> tuple[int | None, UUID | None]:
        if not settings.reservations_service_url:
            return None, None
        url = (
            f"{settings.reservations_service_url}"
            f"/api/v1/reservations/{reservation_id}"
        )
        try:
            response = httpx.get(
                url,
                headers={"X-Internal-Api-Key": settings.internal_api_key},
                timeout=3.0,
            )
            response.raise_for_status()
            data = response.json()
            guests = data.get("number_of_guests")
            property_id = data.get("id_property")
            return (
                int(guests) if guests is not None else None,
                UUID(property_id) if property_id else None,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "reservation_details_fetch_failed",
                extra={"reservation_id": str(reservation_id), "error": str(exc)},
            )
            return None, None


class PropertyDetailsClient:
    def fetch_address(self, property_id: UUID) -> str | None:
        url = settings.properties_service_url
        if not url:
            return None
        try:
            response = httpx.get(
                f"{url}/api/v1/properties/{property_id}",
                timeout=3.0,
            )
            response.raise_for_status()
            data = response.json()
            return data.get("location") or data.get("address")
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "property_details_fetch_failed",
                extra={"property_id": str(property_id), "error": str(exc)},
            )
            return None
