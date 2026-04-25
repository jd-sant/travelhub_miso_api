from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from assembly import (
    get_property_detail_use_case,
    get_properties_list_use_case,
)
from domain.schemas.property import PropertyResponse, PropertyListResponse
from domain.use_cases.get_property_detail import (
    GetPropertyDetailUseCase,
)
from domain.use_cases.get_properties_list import (
    GetPropertiesListUseCase,
)
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
