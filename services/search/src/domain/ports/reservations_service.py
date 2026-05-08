from abc import ABC, abstractmethod
from datetime import date
from uuid import UUID

from domain.schemas.external import AvailabilityResult


class ReservationsServicePort(ABC):
    @abstractmethod
    def availability_check(
        self,
        property_ids: list[UUID],
        check_in: date,
        check_out: date,
    ) -> AvailabilityResult:
        """Call POST /api/v1/internal/reservations/availability-check."""
