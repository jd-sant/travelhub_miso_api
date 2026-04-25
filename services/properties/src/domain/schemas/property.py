from datetime import date
from uuid import UUID

from pydantic import BaseModel, Field


class PropertyImage(BaseModel):
    id: str
    url: str
    alt_text: str | None = None
    position: int
    url_hires: str | None = None
    is_cover: bool = False


class PropertyReview(BaseModel):
    id: str
    author: str
    rating: int = Field(ge=1, le=5)
    review_date: date
    comment: str
    verified_stay: bool


class PropertyResponse(BaseModel):
    id: UUID
    id_owner: UUID | None = None
    name: str
    description: str
    location: str
    latitude: float | None = None
    longitude: float | None = None
    price_per_night: float
    currency: str
    rating: float = Field(ge=0.0, le=5.0)
    review_count: int = Field(ge=0)
    bedrooms: int = Field(ge=0)
    bathrooms: float = Field(ge=0.0)
    max_guests: int = Field(ge=0)
    amenities: list[str]
    cancellation_policy: str
    tax_rate: float
    cleaning_fee: float
    images: list[PropertyImage] = Field(default_factory=list)
    reviews: list[PropertyReview] = Field(default_factory=list)
    status: int = Field(default=1, ge=0, le=1)


class PropertyListResponse(BaseModel):
    """Simplified property response for listing"""
    id: UUID
    id_owner: UUID | None = None
    name: str
    description: str
    location: str
    latitude: float | None = None
    longitude: float | None = None
    price_per_night: float
    currency: str
    rating: float = Field(ge=0.0, le=5.0)
    review_count: int = Field(ge=0)
    bedrooms: int = Field(ge=0)
    bathrooms: float = Field(ge=0.0)
    max_guests: int = Field(ge=0)
    amenities: list[str]
    cancellation_policy: str
    tax_rate: float
    cleaning_fee: float
    images: list[PropertyImage] = Field(default_factory=list)
    status: int = Field(default=1, ge=0, le=1)
