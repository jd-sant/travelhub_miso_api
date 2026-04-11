from uuid import UUID

from domain.ports.property_repository import PropertyRepository
from domain.schemas.property import PropertyResponse
from domain.use_cases.base import BaseUseCase
from errors import PropertyNotFoundError


class GetPropertyDetailUseCase(
    BaseUseCase[UUID, PropertyResponse]
):
    def __init__(self, repository: PropertyRepository):
        self.repository = repository

    def execute(self, property_id: UUID) -> PropertyResponse:
        property_detail = self.repository.get_by_id(property_id)
        if property_detail is None:
            raise PropertyNotFoundError(
                f"Property with id {property_id} not found"
            )
        return property_detail
