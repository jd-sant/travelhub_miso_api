from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status, Request

from core.security import decode_jwt_token

from assembly import (
    get_property_detail_use_case,
    get_properties_list_use_case,
    search_properties_use_case,
    upsert_seasonal_pricing_use_case,
    get_seasonal_pricing_use_case,
)
from domain.schemas.property import (
    PropertyFilters,
    PropertyListResponse,
    PropertyResponse,
    PropertySearchResponse,
    PropertySortBy,
    PropertySortDir,
    SeasonalPricingCreateRequest,
    SeasonalPricingResponse,
    SeasonalPricingListResponse,
)
from domain.use_cases.get_property_detail import (
    GetPropertyDetailUseCase,
)
from domain.use_cases.get_properties_list import (
    GetPropertiesListUseCase,
)
from domain.use_cases.search_properties import SearchPropertiesUseCase
from domain.use_cases.upsert_seasonal_pricing import UpsertSeasonalPricingUseCase
from domain.use_cases.get_seasonal_pricing import GetSeasonalPricingUseCase
from errors import (
    PropertyNotFoundError,
    PricingSignatureVerificationError,
    PricingOwnershipError,
    PricingIntegrityLockedError,
    SeasonalPricingNotFoundError,
)

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
    min_lat: float | None = Query(default=None, ge=-90, le=90),
    max_lat: float | None = Query(default=None, ge=-90, le=90),
    min_lng: float | None = Query(default=None, ge=-180, le=180),
    max_lng: float | None = Query(default=None, ge=-180, le=180),
    status_filter: int | None = Query(default=1, ge=0, le=1, alias="status"),
    check_in: str | None = Query(default=None, description="ISO date YYYY-MM-DD for seasonal pricing"),
    check_out: str | None = Query(default=None, description="ISO date YYYY-MM-DD for seasonal pricing"),
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
        min_lat=min_lat,
        max_lat=max_lat,
        min_lng=min_lng,
        max_lng=max_lng,
        status=status_filter,
        check_in=check_in,
        check_out=check_out,
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


# ===== Seasonal Pricing Endpoints (Admin) =====


def _get_admin_id_and_ip(request: Request) -> tuple[str | None, str | None]:
    """Extract admin ID from JWT Authorization header and IP from request."""
    admin_id = None
    ip = request.client.host if request.client else None
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        payload = decode_jwt_token(auth.split(" ")[1])
        if payload is not None:
            admin_id = payload.get("sub")
    return admin_id, ip


@router.post(
    "/{property_id}/seasonal-pricing",
    response_model=SeasonalPricingResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_seasonal_pricing(
    property_id: UUID,
    request_body: SeasonalPricingCreateRequest,
    request: Request,
    use_case: UpsertSeasonalPricingUseCase = Depends(upsert_seasonal_pricing_use_case),
) -> SeasonalPricingResponse:
    """
    Create seasonal pricing with digital signature.
    
    Admin-only endpoint. Signature is auto-generated and verified before persistence.
    """
    admin_id, source_ip = _get_admin_id_and_ip(request)
    
    try:
        return use_case.execute(
            property_id=property_id,
            admin_id=admin_id,
            source_ip=source_ip,
            request=request_body,
            seasonal_price_id=None,  # Create new
        )
    except PropertyNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except PricingOwnershipError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except PricingSignatureVerificationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.patch(
    "/{property_id}/seasonal-pricing/{seasonal_price_id}",
    response_model=SeasonalPricingResponse,
    status_code=status.HTTP_200_OK,
)
def update_seasonal_pricing(
    property_id: UUID,
    seasonal_price_id: UUID,
    request_body: SeasonalPricingCreateRequest,
    request: Request,
    use_case: UpsertSeasonalPricingUseCase = Depends(upsert_seasonal_pricing_use_case),
) -> SeasonalPricingResponse:
    """
    Update seasonal pricing with digital signature.
    
    Admin-only endpoint. Cannot update if pricing is locked due to integrity failure.
    """
    admin_id, source_ip = _get_admin_id_and_ip(request)
    
    try:
        return use_case.execute(
            property_id=property_id,
            admin_id=admin_id,
            source_ip=source_ip,
            request=request_body,
            seasonal_price_id=seasonal_price_id,  # Update existing
        )
    except PropertyNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except PricingOwnershipError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except PricingSignatureVerificationError as e:
        # 423 Locked si está locked, 400 Bad Request si es otra razón
        if "locked" in str(e).lower():
            raise HTTPException(status_code=status.HTTP_423_LOCKED, detail=str(e))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get(
    "/{property_id}/seasonal-pricing",
    response_model=SeasonalPricingListResponse,
    status_code=status.HTTP_200_OK,
)
def list_seasonal_pricing(
    property_id: UUID,
    use_case: GetSeasonalPricingUseCase = Depends(get_seasonal_pricing_use_case),
) -> SeasonalPricingListResponse:
    """
    List all seasonal pricing for a property.
    
    Validates signature on every read (100% coverage). Locks if tampering detected.
    """
    try:
        return use_case.execute(property_id=property_id, seasonal_price_id=None)
    except PropertyNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get(
    "/{property_id}/seasonal-pricing/{seasonal_price_id}",
    response_model=SeasonalPricingResponse,
    status_code=status.HTTP_200_OK,
)
def get_seasonal_pricing(
    property_id: UUID,
    seasonal_price_id: UUID,
    use_case: GetSeasonalPricingUseCase = Depends(get_seasonal_pricing_use_case),
) -> SeasonalPricingResponse:
    """
    Get single seasonal pricing record.
    
    Validates signature on read. Locks if tampering detected.
    """
    try:
        result = use_case.execute(property_id=property_id, seasonal_price_id=seasonal_price_id)
        # If it's a list response, return first item (shouldn't happen with seasonal_price_id set)
        if isinstance(result, SeasonalPricingListResponse):
            if result.items:
                return result.items[0]
            raise SeasonalPricingNotFoundError("Seasonal pricing not found")
        return result
    except SeasonalPricingNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
