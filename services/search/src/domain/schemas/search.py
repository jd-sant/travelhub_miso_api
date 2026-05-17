from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class PropertySearchItem(BaseModel):
    id: UUID
    name: str
    city: str
    country: str
    max_capacity: int
    main_image_url: str | None
    rating: float | None
    price_from: Decimal
    base_price_from: Decimal | None = None
    has_seasonal_discount: bool = False
    currency: str
    amenities: list[str] = Field(default_factory=list)
    latitude: float | None = None
    longitude: float | None = None


class SearchQuery(BaseModel):
    city: str | None = Field(default=None, min_length=2, max_length=120)
    check_in: date | None = None
    check_out: date | None = None
    guests: int = Field(ge=1)
    amenities: list[str] = Field(default_factory=list)
    min_price: Decimal | None = Field(default=None, ge=0)
    max_price: Decimal | None = Field(default=None, ge=0)
    min_lat: float | None = Field(default=None, ge=-90, le=90)
    max_lat: float | None = Field(default=None, ge=-90, le=90)
    min_lng: float | None = Field(default=None, ge=-180, le=180)
    max_lng: float | None = Field(default=None, ge=-180, le=180)
    order_by: str = Field(default="price")
    order_dir: str = Field(default="asc")
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=10, ge=1, le=100)


class SearchResult(BaseModel):
    items: list[PropertySearchItem]
    total: int
    page: int
    page_size: int


class SearchPagination(BaseModel):
    total: int
    page: int
    page_size: int
    total_pages: int


class EmptyStateSuggestion(BaseModel):
    code: str
    message: str


class SearchResponse(BaseModel):
    items: list[PropertySearchItem]
    pagination: SearchPagination
    empty_state: list[EmptyStateSuggestion] = Field(default_factory=list)
