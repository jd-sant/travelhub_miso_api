from datetime import date
from uuid import UUID

from domain.ports.property_repository import PropertyRepository
from domain.schemas.property import PropertyResponse
from errors import PropertyNotFoundError


class GetPropertyDetailUseCase:
    def __init__(self, repository: PropertyRepository):
        self.repository = repository

    def execute(
        self,
        property_id: UUID,
        check_in: date | None = None,
        check_out: date | None = None,
    ) -> PropertyResponse:
        property_detail = self.repository.get_by_id(property_id, check_in, check_out)
        if property_detail is None:
            raise PropertyNotFoundError(
                f"Property with id {property_id} not found"
            )
        return property_detail
