from abc import ABC, abstractmethod
from typing import Optional
from uuid import UUID

from domain.schemas.property import PropertyResponse, PropertyListResponse


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
