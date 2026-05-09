from domain.ports.property_repository import PropertyRepository
from domain.schemas.property import PropertyFilters, PropertySearchResponse
from domain.use_cases.base import BaseUseCase


class SearchPropertiesUseCase(BaseUseCase[PropertyFilters, PropertySearchResponse]):
    def __init__(self, repository: PropertyRepository):
        self.repository = repository

    def execute(self, filters: PropertyFilters) -> PropertySearchResponse:
        return self.repository.search(filters)
