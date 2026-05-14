from abc import ABC, abstractmethod
from datetime import date
from uuid import UUID

from domain.schemas.availability import PropertyAvailabilityResponse


class InventoryServicePort(ABC):
    @abstractmethod
    def get_availability(
        self,
        property_id: UUID,
        check_in: date,
        check_out: date,
        guests: int,
    ) -> PropertyAvailabilityResponse:
        """Call Inventory and return availability plus effective price."""
