from datetime import datetime, time

from domain.ports.reservation_repository import ReservationRepository
from domain.schemas.reservation import (
    AvailabilityCheckRequest,
    AvailabilityCheckResponse,
)
from errors import InvalidReservationStatusError


class CheckPropertiesAvailabilityUseCase:
    def __init__(self, repository: ReservationRepository):
        self.repository = repository

    def execute(self, payload: AvailabilityCheckRequest) -> AvailabilityCheckResponse:
        if payload.check_out <= payload.check_in:
            raise InvalidReservationStatusError(
                "check_out must be strictly after check_in"
            )

        check_in_dt = datetime.combine(payload.check_in, time.min)
        check_out_dt = datetime.combine(payload.check_out, time.min)

        available, blocked = self.repository.check_properties_availability(
            payload.property_ids, check_in_dt, check_out_dt
        )
        return AvailabilityCheckResponse(available=available, blocked=blocked)
