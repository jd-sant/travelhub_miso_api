"""Servicio de enriquecimiento best-effort para la confirmación de pago.

Encadena las consultas HTTP a `reservations` (huéspedes + id_property) y a
`properties` (dirección) para ofrecer al viajero el detalle completo exigido
por HU022 sin acoplar al use case a los detalles de transporte.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from adapters.services.reservation_details_client import (
    PropertyDetailsClient,
    ReservationDetailsClient,
)


@dataclass(frozen=True)
class ConfirmationEnrichment:
    guests_count: int | None
    property_address: str | None


class ConfirmationEnrichmentService:
    def __init__(
        self,
        reservation_details_client: ReservationDetailsClient | None = None,
        property_details_client: PropertyDetailsClient | None = None,
    ):
        self._reservations = reservation_details_client or ReservationDetailsClient()
        self._properties = property_details_client or PropertyDetailsClient()

    def enrich(self, reservation_id: UUID) -> ConfirmationEnrichment:
        guests, property_id = self._reservations.fetch_guests_and_property(reservation_id)
        address = (
            self._properties.fetch_address(property_id) if property_id is not None else None
        )
        return ConfirmationEnrichment(guests_count=guests, property_address=address)
