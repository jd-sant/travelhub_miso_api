"""DTOs for data fetched from other microservices via HTTP."""
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class PropertyImage(BaseModel):
    url: str | None = None
    is_cover: bool = False


class PropertyMetadata(BaseModel):
    """Subset of properties.PropertyListResponse used by search to build results."""

    id: UUID
    name: str
    location: str
    price_per_night: Decimal
    currency: str
    rating: float = 0.0
    max_guests: int = 0
    amenities: list[str] = Field(default_factory=list)
    status: int = 1
    images: list[PropertyImage] = Field(default_factory=list)
    latitude: float | None = None
    longitude: float | None = None

    def cover_image_url(self) -> str | None:
        for img in self.images:
            if img.is_cover and img.url:
                return img.url
        for img in self.images:
            if img.url:
                return img.url
        return None

    def split_location(self) -> tuple[str, str]:
        """Parse "City, Country" into (city, country)."""
        parts = self.location.split(",", 1)
        city = parts[0].strip() if parts else ""
        country = parts[1].strip() if len(parts) > 1 else ""
        return city, country


class PropertiesPage(BaseModel):
    items: list[PropertyMetadata]
    total: int
    page: int
    page_size: int
    total_pages: int


class AvailabilityResult(BaseModel):
    available: list[UUID] = Field(default_factory=list)
    blocked: list[UUID] = Field(default_factory=list)
