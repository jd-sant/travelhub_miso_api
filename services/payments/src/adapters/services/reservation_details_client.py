"""Cliente HTTP best-effort para obtener detalles de reserva/propiedad.

Se usa al construir la confirmación de pago para enriquecer el payload con
número de huéspedes, dirección de la propiedad, nombre de la propiedad y
fechas de check-in/check-out. Cualquier fallo devuelve campos nulos;
el correo sigue enviándose con los datos disponibles.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID

import httpx

from core.config import settings

logger = logging.getLogger(__name__)


def _parse_date(value) -> date | None:
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()
    except (TypeError, ValueError):
        return None


@dataclass(frozen=True)
class ReservationDetails:
    guests_count: int | None
    property_id: UUID | None
    check_in_date: date | None
    check_out_date: date | None


@dataclass(frozen=True)
class PropertyDetails:
    name: str | None
    address: str | None


class ReservationDetailsClient:
    def fetch(self, reservation_id: UUID) -> ReservationDetails:
        empty = ReservationDetails(None, None, None, None)
        if not settings.reservations_service_url:
            return empty
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
            return ReservationDetails(
                guests_count=int(guests) if guests is not None else None,
                property_id=UUID(property_id) if property_id else None,
                check_in_date=_parse_date(data.get("check_in_date")),
                check_out_date=_parse_date(data.get("check_out_date")),
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "reservation_details_fetch_failed",
                extra={"reservation_id": str(reservation_id), "error": str(exc)},
            )
            return empty


class PropertyDetailsClient:
    def fetch(self, property_id: UUID) -> PropertyDetails:
        empty = PropertyDetails(None, None)
        url = settings.properties_service_url
        if not url:
            return empty
        try:
            response = httpx.get(
                f"{url}/api/v1/properties/{property_id}",
                timeout=3.0,
            )
            response.raise_for_status()
            data = response.json()
            return PropertyDetails(
                name=data.get("name"),
                address=data.get("location") or data.get("address"),
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "property_details_fetch_failed",
                extra={"property_id": str(property_id), "error": str(exc)},
            )
            return empty
