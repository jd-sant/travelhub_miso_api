from dataclasses import dataclass
from datetime import date
from uuid import UUID

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Query,
    Request,
    status,
)

from adapters.services.search_client import invalidate_search_cache
from assembly import (
    get_properties_list_use_case,
    get_property_detail_use_case,
    get_seasonal_pricing_use_case,
    get_security_client,
    search_properties_use_case,
    unlock_seasonal_pricing_use_case,
    upsert_seasonal_pricing_use_case,
)
from adapters.services.security_client import SecurityClient
from domain.schemas.property import (
    PropertyFilters,
    PropertyListResponse,
    PropertyResponse,
    PropertySearchResponse,
    PropertySortBy,
    PropertySortDir,
    SeasonalPricingCreateRequest,
    SeasonalPricingListResponse,
    SeasonalPricingResponse,
    SeasonalPricingUpdateRequest,
    SeasonalUnlockRequest,
)
from domain.use_cases.get_properties_list import GetPropertiesListUseCase
from domain.use_cases.get_property_detail import GetPropertyDetailUseCase
from domain.use_cases.get_seasonal_pricing import GetSeasonalPricingUseCase
from domain.use_cases.search_properties import SearchPropertiesUseCase
from domain.use_cases.unlock_seasonal_pricing import UnlockSeasonalPricingUseCase
from domain.use_cases.upsert_seasonal_pricing import UpsertSeasonalPricingUseCase
from errors import (
    AuthenticationError,
    PricingIntegrityLockedError,
    PricingOwnershipError,
    PricingSignatureVerificationError,
    PropertyNotFoundError,
    SeasonalPricingNotFoundError,
)

router = APIRouter(prefix="/properties", tags=["properties"])


# ===== Admin auth context =====


@dataclass(frozen=True)
class AdminContext:
    admin_id: str
    role: str
    source_ip: str | None


def _client_ip(request: Request) -> str | None:
    """Prefer the first hop in X-Forwarded-For (set by ALB/ingress) over the
    socket peer, which is the proxy itself in production."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        first = forwarded.split(",")[0].strip()
        if first:
            return first
    return request.client.host if request.client else None


def get_current_admin(
    request: Request,
    security_client: SecurityClient = Depends(get_security_client),
) -> AdminContext:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    token = auth.split(" ", 1)[1].strip()
    claims = security_client.validate_token(token)
    if claims is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    return AdminContext(
        admin_id=str(claims.user_id),
        role=claims.role,
        source_ip=_client_ip(request),
    )


# ===== Public endpoints =====


@router.get(
    "",
    response_model=list[PropertyListResponse],
    status_code=status.HTTP_200_OK,
)
def list_properties(
    owner_id: UUID | None = Query(default=None),
    use_case: GetPropertiesListUseCase = Depends(get_properties_list_use_case),
) -> list[PropertyListResponse]:
    """Get available properties, optionally scoped to a specific owner."""
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
    check_in: date | None = Query(default=None),
    check_out: date | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    sort_by: PropertySortBy = Query(default=PropertySortBy.PRICE),
    sort_dir: PropertySortDir = Query(default=PropertySortDir.ASC),
    use_case: SearchPropertiesUseCase = Depends(search_properties_use_case),
) -> PropertySearchResponse:
    """Search properties with filters, sort and pagination."""
    if (check_in is None) ^ (check_out is None):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="check_in and check_out must be provided together",
        )
    if check_in is not None and check_out is not None and check_out <= check_in:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="check_out must be after check_in",
        )

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
    check_in: date | None = Query(default=None),
    check_out: date | None = Query(default=None),
    use_case: GetPropertyDetailUseCase = Depends(get_property_detail_use_case),
) -> PropertyResponse:
    """Get details of a specific property (images, amenities, reviews, ratings).

    When `check_in` and `check_out` are provided, the response's
    `price_per_night` reflects the active seasonal pricing override (if any)
    so the booking widget can show the customer the price they will be
    charged. Both must be provided together.
    """
    if (check_in is None) ^ (check_out is None):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="check_in and check_out must be provided together",
        )
    if check_in is not None and check_out is not None and check_out <= check_in:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="check_out must be after check_in",
        )
    try:
        return use_case.execute(property_id, check_in, check_out)
    except PropertyNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Property with id {property_id} not found",
        )


# ===== Seasonal Pricing Endpoints (Admin) =====


def _schedule_search_invalidation(background: BackgroundTasks) -> None:
    background.add_task(invalidate_search_cache)


@router.post(
    "/{property_id}/seasonal-pricing",
    response_model=SeasonalPricingResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_seasonal_pricing(
    property_id: UUID,
    request_body: SeasonalPricingCreateRequest,
    background: BackgroundTasks,
    admin: AdminContext = Depends(get_current_admin),
    use_case: UpsertSeasonalPricingUseCase = Depends(upsert_seasonal_pricing_use_case),
) -> SeasonalPricingResponse:
    """Create seasonal pricing with digital signature (admin-only)."""
    try:
        response = use_case.execute_create(
            property_id=property_id,
            admin_id=admin.admin_id,
            source_ip=admin.source_ip,
            request=request_body,
        )
    except PropertyNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except PricingOwnershipError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except PricingSignatureVerificationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    _schedule_search_invalidation(background)
    return response


@router.patch(
    "/{property_id}/seasonal-pricing/{seasonal_price_id}",
    response_model=SeasonalPricingResponse,
    status_code=status.HTTP_200_OK,
)
def update_seasonal_pricing(
    property_id: UUID,
    seasonal_price_id: UUID,
    request_body: SeasonalPricingUpdateRequest,
    background: BackgroundTasks,
    admin: AdminContext = Depends(get_current_admin),
    use_case: UpsertSeasonalPricingUseCase = Depends(upsert_seasonal_pricing_use_case),
) -> SeasonalPricingResponse:
    """Partially update seasonal pricing (admin-only).

    Refuses to operate on records locked by integrity failure (423).
    """
    try:
        response = use_case.execute_update(
            property_id=property_id,
            seasonal_price_id=seasonal_price_id,
            admin_id=admin.admin_id,
            source_ip=admin.source_ip,
            request=request_body,
        )
    except PropertyNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except SeasonalPricingNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except PricingOwnershipError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except PricingIntegrityLockedError as exc:
        raise HTTPException(status_code=status.HTTP_423_LOCKED, detail=str(exc))
    except PricingSignatureVerificationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    _schedule_search_invalidation(background)
    return response


@router.post(
    "/{property_id}/seasonal-pricing/{seasonal_price_id}/unlock",
    response_model=SeasonalPricingResponse,
    status_code=status.HTTP_200_OK,
)
def unlock_seasonal_pricing(
    property_id: UUID,
    seasonal_price_id: UUID,
    request_body: SeasonalUnlockRequest,
    background: BackgroundTasks,
    admin: AdminContext = Depends(get_current_admin),
    use_case: UnlockSeasonalPricingUseCase = Depends(unlock_seasonal_pricing_use_case),
) -> SeasonalPricingResponse:
    """Clear the integrity lock on a pricing record after manual review.

    Re-signs the current state as a new baseline and writes an audit entry.
    """
    try:
        response = use_case.execute(
            property_id=property_id,
            seasonal_price_id=seasonal_price_id,
            admin_id=admin.admin_id,
            source_ip=admin.source_ip,
            reason=request_body.reason,
        )
    except PropertyNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except SeasonalPricingNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except PricingOwnershipError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))

    _schedule_search_invalidation(background)
    return response


@router.get(
    "/{property_id}/seasonal-pricing",
    response_model=SeasonalPricingListResponse,
    status_code=status.HTTP_200_OK,
)
def list_seasonal_pricing(
    property_id: UUID,
    use_case: GetSeasonalPricingUseCase = Depends(get_seasonal_pricing_use_case),
) -> SeasonalPricingListResponse:
    """List all seasonal pricing for a property.

    Validates signature on every read (100% coverage). Locks if tampering detected.
    """
    return use_case.execute(property_id=property_id, seasonal_price_id=None)


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
    """Get a single seasonal pricing record (signature validated on read)."""
    try:
        return use_case.execute(
            property_id=property_id, seasonal_price_id=seasonal_price_id
        )
    except SeasonalPricingNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
