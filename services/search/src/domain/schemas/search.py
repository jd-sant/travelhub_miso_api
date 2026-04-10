from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PropertySearchItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: UUID
    name: str = Field(alias="nombre")
    city: str = Field(alias="ciudad")
    country: str = Field(alias="pais")
    max_capacity: int = Field(alias="capacidad_maxima")
    main_image_url: str | None = Field(alias="imagen_principal_url")
    rating: float | None
    price_from: Decimal = Field(alias="precio_desde")
    currency: str = Field(alias="moneda")
    amenities: list[str] = Field(default_factory=list, alias="amenidades")


class SearchQuery(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    city: str = Field(min_length=2, max_length=120, alias="ciudad")
    check_in: date
    check_out: date
    guests: int = Field(ge=1, alias="huespedes")
    amenities: list[str] = Field(default_factory=list, alias="amenidades")
    min_price: Decimal | None = Field(default=None, ge=0, alias="precio_min")
    max_price: Decimal | None = Field(default=None, ge=0, alias="precio_max")
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
    model_config = ConfigDict(populate_by_name=True)

    items: list[PropertySearchItem]
    pagination: SearchPagination
    empty_state: list[EmptyStateSuggestion] = Field(default_factory=list)
