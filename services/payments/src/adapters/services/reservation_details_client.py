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
class ReservationPriceBreakdown:
    accommodation_in_cents: int
    cleaning_fee_in_cents: int
    service_fee_in_cents: int
    taxes_in_cents: int
    total_in_cents: int
    nights: int
    nightly_rate_in_cents: int
    currency: str


@dataclass(frozen=True)
class ReservationDetails:
    guests_count: int | None
    property_id: UUID | None
    check_in_date: date | None
    check_out_date: date | None
    price_breakdown: ReservationPriceBreakdown | None = None


@dataclass(frozen=True)
class PropertyDetails:
    name: str | None
    address: str | None


def _parse_breakdown(value) -> ReservationPriceBreakdown | None:
    if not isinstance(value, dict):
        return None
    try:
        return ReservationPriceBreakdown(
            accommodation_in_cents=int(value.get("accommodation_in_cents") or 0),
            cleaning_fee_in_cents=int(value.get("cleaning_fee_in_cents") or 0),
            service_fee_in_cents=int(value.get("service_fee_in_cents") or 0),
            taxes_in_cents=int(value.get("taxes_in_cents") or 0),
            total_in_cents=int(value.get("total_in_cents") or 0),
            nights=int(value.get("nights") or 0),
            nightly_rate_in_cents=int(value.get("nightly_rate_in_cents") or 0),
            currency=str(value.get("currency") or ""),
        )
    except (TypeError, ValueError):
        return None


class ReservationDetailsClient:
    def fetch(self, reservation_id: UUID) -> ReservationDetails:
        empty = ReservationDetails(None, None, None, None, None)
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
                price_breakdown=_parse_breakdown(data.get("price_breakdown")),
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
