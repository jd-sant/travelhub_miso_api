from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from assembly import (
    get_property_detail_use_case,
    get_properties_list_use_case,
    search_properties_use_case,
)
from domain.schemas.property import (
    PropertyFilters,
    PropertyListResponse,
    PropertyResponse,
    PropertySearchResponse,
    PropertySortBy,
    PropertySortDir,
)
from domain.use_cases.get_property_detail import (
    GetPropertyDetailUseCase,
)
from domain.use_cases.get_properties_list import (
    GetPropertiesListUseCase,
)
from domain.use_cases.search_properties import SearchPropertiesUseCase
from errors import PropertyNotFoundError

router = APIRouter(prefix="/properties", tags=["properties"])


@router.get(
    "",
    response_model=list[PropertyListResponse],
    status_code=status.HTTP_200_OK,
)
def list_properties(
    owner_id: UUID | None = Query(default=None),
    use_case: GetPropertiesListUseCase = Depends(
        get_properties_list_use_case
    ),
) -> list[PropertyListResponse]:
    """
    Get available properties, optionally scoped to a specific owner.
    """
    return use_case.execute(owner_id=owner_id)


@router.get(
    "/search",
    response_model=PropertySearchResponse,
    status_code=status.HTTP_200_OK,
)
def search_properties(
    city: str | None = Query(default=None, max_length=120),
    min_price: float | None = Query(default=None, ge=0),
    max_price: float | None = Query(default=None, ge=0),
    min_guests: int | None = Query(default=None, ge=1),
    amenities: list[str] = Query(default_factory=list),
    ids: list[UUID] = Query(default_factory=list),
    status_filter: int | None = Query(default=1, ge=0, le=1, alias="status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    sort_by: PropertySortBy = Query(default=PropertySortBy.PRICE),
    sort_dir: PropertySortDir = Query(default=PropertySortDir.ASC),
    use_case: SearchPropertiesUseCase = Depends(search_properties_use_case),
) -> PropertySearchResponse:
    """Search properties with filters, sort and pagination."""
    filters = PropertyFilters(
        city=city,
        min_price=min_price,
        max_price=max_price,
        min_guests=min_guests,
        amenities=amenities,
        ids=ids,
        status=status_filter,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )
    return use_case.execute(filters)


@router.get(
    "/{property_id}",
    response_model=PropertyResponse,
    status_code=status.HTTP_200_OK,
)
def get_property_detail(
    property_id: UUID,
    use_case: GetPropertyDetailUseCase = Depends(
        get_property_detail_use_case
    ),
) -> PropertyResponse:
    """
    Get details of a specific property.

    Includes all information: images, amenities, reviews, and ratings.
    """
    try:
        return use_case.execute(property_id)
    except PropertyNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Property with id {property_id} not found",
        )
