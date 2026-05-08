from abc import ABC, abstractmethod
from typing import Optional
from uuid import UUID

from domain.schemas.property import (
    PropertyFilters,
    PropertyListResponse,
    PropertyResponse,
    PropertySearchResponse,
)
from domain.schemas.property_policy import PropertyCancellationPolicyResponse


class PropertyRepository(ABC):
    @abstractmethod
    def get_by_id(self, property_id: UUID) -> Optional[PropertyResponse]:
        """Get a property by ID with all related data including images and reviews"""
        pass

    @abstractmethod
    def list_all(
        self, owner_id: Optional[UUID] = None
    ) -> list[PropertyListResponse]:
        """List properties with their images, optionally filtered by owner."""
        pass

    @abstractmethod
    def search(self, filters: PropertyFilters) -> PropertySearchResponse:
        """Search properties with filters, sort and pagination."""
        pass

    @abstractmethod
    def get_cancellation_policy(
        self, property_id: UUID
    ) -> Optional[PropertyCancellationPolicyResponse]:
        """Get the active cancellation policy for a property"""
        pass
