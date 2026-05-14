from datetime import date
from enum import Enum
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


class PropertySortBy(str, Enum):
    PRICE = "price"
    RATING = "rating"
    NAME = "name"


class PropertySortDir(str, Enum):
    ASC = "asc"
    DESC = "desc"


class PropertyFilters(BaseModel):
    city: str | None = None
    min_price: float | None = Field(default=None, ge=0)
    max_price: float | None = Field(default=None, ge=0)
    min_guests: int | None = Field(default=None, ge=1)
    amenities: list[str] = Field(default_factory=list)
    ids: list[UUID] = Field(default_factory=list)
    status: int | None = Field(default=1, ge=0, le=1)
    check_in: str | None = Field(default=None, description="ISO date YYYY-MM-DD for seasonal pricing lookup")
    check_out: str | None = Field(default=None, description="ISO date YYYY-MM-DD for seasonal pricing lookup")
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
    sort_by: PropertySortBy = PropertySortBy.PRICE
    sort_dir: PropertySortDir = PropertySortDir.ASC


class PaginationMeta(BaseModel):
    total: int
    page: int
    page_size: int
    total_pages: int


class PropertySearchResponse(BaseModel):
    items: list[PropertyListResponse]
    pagination: PaginationMeta


# ===== Seasonal Pricing Schemas (Firmado) =====

class SeasonalPricingCreateRequest(BaseModel):
    """Request para crear pricing estacional firmado"""
    season_start: str = Field(..., description="Fecha inicio YYYY-MM-DD")
    season_end: str = Field(..., description="Fecha fin YYYY-MM-DD")
    price_per_night: float = Field(..., ge=0)
    currency: str = Field(default="COP", min_length=3, max_length=3)
    tax_rate: float = Field(default=0.0, ge=0.0)
    cleaning_fee: float = Field(default=0.0, ge=0.0)


class SeasonalPricingResponse(BaseModel):
    """Response de pricing estacional con estado de integridad"""
    id: UUID
    property_id: UUID
    season_start: str
    season_end: str
    price_per_night: float
    currency: str
    tax_rate: float
    cleaning_fee: float
    signature_hash: str
    signature_algo: str
    integrity_locked: bool
    integrity_checked_at: str | None = None
    created_at: str
    updated_at: str
    integrity_valid: bool = True  # Resultado de verificacion en lectura


class SeasonalPricingListResponse(BaseModel):
    """Lista de precios estacionales de una propiedad"""
    items: list[SeasonalPricingResponse]
    total: int


class IntegrityCheckResult(BaseModel):
    """Resultado de verificacion de integridad"""
    is_valid: bool
    signature_hash: str
    locked: bool
    message: str
