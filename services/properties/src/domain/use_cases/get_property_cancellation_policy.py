from uuid import UUID

from domain.ports.property_repository import PropertyRepository
from domain.schemas.property_policy import PropertyCancellationPolicyResponse
from domain.use_cases.base import BaseUseCase
from errors import PropertyNotFoundError


class GetPropertyCancellationPolicyUseCase(
    BaseUseCase[UUID, PropertyCancellationPolicyResponse]
):
    def __init__(self, repository: PropertyRepository):
        self.repository = repository

    def execute(self, property_id: UUID) -> PropertyCancellationPolicyResponse:
        policy = self.repository.get_cancellation_policy(property_id)
        if not policy:
            raise PropertyNotFoundError("Cancellation policy not found")
        return policy
