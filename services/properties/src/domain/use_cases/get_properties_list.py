from domain.ports.property_repository import PropertyRepository
from domain.schemas.property import PropertyListResponse
from domain.use_cases.base import BaseUseCase


class GetPropertiesListUseCase(BaseUseCase[None, list[PropertyListResponse]]):
    def __init__(self, repository: PropertyRepository):
        self.repository = repository

    def execute(self, *args, **kwargs) -> list[PropertyListResponse]:
        """Get all properties"""
        return self.repository.list_all()
