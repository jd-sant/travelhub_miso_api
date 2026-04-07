from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class PropertySearchItem(BaseModel):
    id: UUID
    nombre: str
    ciudad: str
    pais: str
    capacidad_maxima: int
    imagen_principal_url: str | None
    rating: float | None
    precio_desde: Decimal
    moneda: str
    amenidades: list[str] = []


class SearchQuery(BaseModel):
    ciudad: str = Field(min_length=2, max_length=120)
    check_in: date
    check_out: date
    huespedes: int = Field(ge=1)
    amenidades: list[str] = []
    precio_min: Decimal | None = Field(default=None, ge=0)
    precio_max: Decimal | None = Field(default=None, ge=0)
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
    empty_state: list[EmptyStateSuggestion] = []
