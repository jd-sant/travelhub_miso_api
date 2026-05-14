from abc import ABC, abstractmethod
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from domain.schemas.external import PropertiesPage, PropertyMetadata


class PropertyQuery(BaseModel):
    city: str | None = None
    min_price: Decimal | None = None
    max_price: Decimal | None = None
    min_guests: int | None = None
    amenities: list[str] = Field(default_factory=list)
    ids: list[UUID] = Field(default_factory=list)
    min_lat: float | None = None
    max_lat: float | None = None
    min_lng: float | None = None
    max_lng: float | None = None
    sort_by: str = "price"
    sort_dir: str = "asc"
    page: int = 1
    page_size: int = 10


class PropertiesServicePort(ABC):
    @abstractmethod
    def search(self, query: PropertyQuery) -> PropertiesPage:
        """Call GET /api/v1/properties/search and return a paginated result."""

    @abstractmethod
    def get_by_id(self, property_id: UUID) -> PropertyMetadata | None:
        """Call GET /api/v1/properties/{id}. Returns None if 404."""
