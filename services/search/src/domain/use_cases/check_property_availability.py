"""CheckPropertyAvailabilityUseCase: combines properties.status with reservations overlap."""
from decimal import Decimal

from domain.ports.inventory_service import InventoryServicePort
from domain.ports.properties_service import PropertiesServicePort
from domain.ports.reservations_service import ReservationsServicePort
from domain.schemas.availability import (
    PropertyAvailabilityQuery,
    PropertyAvailabilityResponse,
)
from domain.use_cases.base import BaseUseCase
from errors import InventoryServiceUnavailableError


class CheckPropertyAvailabilityUseCase(
    BaseUseCase[PropertyAvailabilityQuery, PropertyAvailabilityResponse]
):
    def __init__(
        self,
        properties: PropertiesServicePort,
        reservations: ReservationsServicePort,
        inventory: InventoryServicePort | None = None,
    ):
        self._properties = properties
        self._reservations = reservations
        self._inventory = inventory

    def execute(self, query: PropertyAvailabilityQuery) -> PropertyAvailabilityResponse:
        if self._inventory is not None:
            try:
                return self._inventory.get_availability(
                    query.property_id,
                    query.check_in,
                    query.check_out,
                    query.guests,
                )
            except InventoryServiceUnavailableError:
                pass

        prop = self._properties.get_by_id(query.property_id)
        unavailable = PropertyAvailabilityResponse(
            property_id=query.property_id,
            check_in=query.check_in,
            check_out=query.check_out,
            guests=query.guests,
            available=False,
        )
        if prop is None or prop.status != 1 or prop.max_guests < query.guests:
            return unavailable

        availability = self._reservations.availability_check(
            [query.property_id], query.check_in, query.check_out
        )
        if query.property_id not in set(availability.available):
            return unavailable

        return PropertyAvailabilityResponse(
            property_id=query.property_id,
            check_in=query.check_in,
            check_out=query.check_out,
            guests=query.guests,
            available=True,
            price_from=Decimal(str(prop.price_per_night)),
            currency=prop.currency,
        )
