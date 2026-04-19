"""Servicio de enriquecimiento best-effort para la confirmación de pago.

Encadena las consultas HTTP a `reservations` (huéspedes, id_property, fechas)
y a `properties` (nombre, dirección) para ofrecer al viajero el detalle
completo exigido por HU022 sin acoplar al use case a los detalles de transporte.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from uuid import UUID

from adapters.services.reservation_details_client import (
    PropertyDetails,
    PropertyDetailsClient,
    ReservationDetailsClient,
)


@dataclass(frozen=True)
class ConfirmationEnrichment:
    guests_count: int | None
    property_name: str | None
    property_address: str | None
    check_in_date: date | None
    check_out_date: date | None


class ConfirmationEnrichmentService:
    def __init__(
        self,
        reservation_details_client: ReservationDetailsClient | None = None,
        property_details_client: PropertyDetailsClient | None = None,
    ):
        self._reservations = reservation_details_client or ReservationDetailsClient()
        self._properties = property_details_client or PropertyDetailsClient()

    def enrich(self, reservation_id: UUID) -> ConfirmationEnrichment:
        reservation = self._reservations.fetch(reservation_id)
        property_details = (
            self._properties.fetch(reservation.property_id)
            if reservation.property_id is not None
            else PropertyDetails(None, None)
        )
        return ConfirmationEnrichment(
            guests_count=reservation.guests_count,
            property_name=property_details.name,
            property_address=property_details.address,
            check_in_date=reservation.check_in_date,
            check_out_date=reservation.check_out_date,
        )
