from domain.ports.search_repository import SearchRepository
from domain.schemas.availability import (
    PropertyAvailabilityQuery,
    PropertyAvailabilityResponse,
)
from domain.use_cases.base import BaseUseCase


class CheckPropertyAvailabilityUseCase(
    BaseUseCase[PropertyAvailabilityQuery, PropertyAvailabilityResponse]
):
    def __init__(self, repository: SearchRepository):
        self.repository = repository

    def execute(
        self, query: PropertyAvailabilityQuery
    ) -> PropertyAvailabilityResponse:
        return self.repository.check_availability(query)
