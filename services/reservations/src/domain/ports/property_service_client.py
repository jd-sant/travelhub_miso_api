from abc import ABC, abstractmethod
from uuid import UUID

from domain.schemas.property_service import (
    PropertyCancellationPolicyResponse,
    PropertyDetailResponse,
)


class PropertyServiceClient(ABC):
    @abstractmethod
    def get_property(self, property_id: UUID) -> PropertyDetailResponse:
        pass

    @abstractmethod
    def get_cancellation_policy(
        self, property_id: UUID
    ) -> PropertyCancellationPolicyResponse:
        pass
