from datetime import date
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session, select

from assembly import (
    get_property_availability_use_case,
    get_pricing_management_use_case,
    get_search_properties_use_case,
)
from adapters.models import Amenity
from adapters.models import InventoryCalendar
from adapters.models import Property
from adapters.models import PropertyAmenity
from adapters.models import RateCalendar
from adapters.models import RatePlan
from adapters.models import RoomType
from adapters.models import Service
from core.auth import AuthenticatedUser, get_current_hotel_user
from core.config import settings
from db.session import get_session
from db.session import engine
from domain.schemas import (
    EmptyStateSuggestion,
    PropertyAvailabilityQuery,
    PropertyAvailabilityResponse,
)
from domain.schemas import SearchPagination
from domain.schemas import SearchQuery
from domain.schemas import SearchResponse
from domain.schemas.pricing import (
    PricingApplyRequest,
    PricingApplyResponse,
    PricingHistoryItem,
    PricingPreviewRequest,
    PricingPreviewResponse,
    PricingRevertResponse,
    PricingTargetOption,
)
from domain.use_cases import (
    CheckPropertyAvailabilityUseCase,
    PricingManagementUseCase,
    SearchPropertiesUseCase,
)
from errors import (
    InvalidSearchRuleError,
    PricingAuthorizationError,
    PricingConflictError,
    PricingTargetNotFoundError,
    PricingValidationError,
    PropertiesServiceUnavailableError,
    ReservationsServiceUnavailableError,
)

router = APIRouter(prefix="/search", tags=["search"])


@router.get("/status")
def search_status() -> dict[str, str]:
    return {"service": "search", "status": "ok"}


@router.get(
    "",
    response_model=SearchResponse,
    responses={
        400: {"description": "Invalid search business rules"},
        422: {"description": "Invalid or missing request fields"},
    },
)
def search_properties(
    city: str = Query(min_length=2, max_length=120),
    check_in: date = Query(),
    check_out: date = Query(),
    guests: int = Query(ge=1),
    amenities: list[str] = Query(default=[]),
    min_price: Decimal | None = Query(default=None, ge=0),
    max_price: Decimal | None = Query(default=None, ge=0),
    order_by: str = Query(default="price"),
    order_dir: str = Query(default="asc"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    use_case: SearchPropertiesUseCase = Depends(get_search_properties_use_case),
) -> SearchResponse:
    try:
        query = SearchQuery(
            city=city,
            check_in=check_in,
            check_out=check_out,
            guests=guests,
            amenities=amenities,
            min_price=min_price,
            max_price=max_price,
            order_by=order_by,
            order_dir=order_dir,
            page=page,
            page_size=page_size,
        )
        _validate_search_rules(query)
        result = use_case.execute(query)
        total_pages = _calculate_total_pages(result.total, result.page_size)

        empty_state = []
        if result.total == 0:
            empty_state = [
                EmptyStateSuggestion(
                    code="TRY_OTHER_CITY",
                    message="No encontramos resultados en esa ciudad. Intenta otra ciudad cercana.",
                ),
                EmptyStateSuggestion(
                    code="TRY_OTHER_DATES",
                    message="Prueba con fechas diferentes para encontrar mayor disponibilidad.",
                ),
            ]
        elif not result.items:
            empty_state = [
                EmptyStateSuggestion(
                    code="TRY_OTHER_DATES",
                    message="Prueba con fechas diferentes para encontrar mayor disponibilidad.",
                ),
            ]

        return SearchResponse(
            items=result.items,
            pagination=SearchPagination(
                total=result.total,
                page=result.page,
                page_size=result.page_size,
                total_pages=total_pages,
            ),
            empty_state=empty_state,
        )
    except InvalidSearchRuleError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except (PropertiesServiceUnavailableError, ReservationsServiceUnavailableError) as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))


@router.get(
    "/properties/{property_id}/availability",
    response_model=PropertyAvailabilityResponse,
)
def check_property_availability(
    property_id: UUID,
    check_in: date = Query(),
    check_out: date = Query(),
    guests: int = Query(ge=1),
    use_case: CheckPropertyAvailabilityUseCase = Depends(get_property_availability_use_case),
) -> PropertyAvailabilityResponse:
    try:
        _validate_search_rules(
            SearchQuery(
                city="placeholder",
                check_in=check_in,
                check_out=check_out,
                guests=guests,
            )
        )
        return use_case.execute(
            PropertyAvailabilityQuery(
                property_id=property_id,
                check_in=check_in,
                check_out=check_out,
                guests=guests,
            )
        )
    except InvalidSearchRuleError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except (PropertiesServiceUnavailableError, ReservationsServiceUnavailableError) as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))


@router.get("/hotel/pricing/targets", response_model=list[PricingTargetOption])
def list_pricing_targets(
    user: AuthenticatedUser = Depends(get_current_hotel_user),
    use_case: PricingManagementUseCase = Depends(get_pricing_management_use_case),
) -> list[PricingTargetOption]:
    return use_case.list_targets(user)


@router.post("/hotel/pricing/preview", response_model=PricingPreviewResponse)
def preview_pricing_change(
    payload: PricingPreviewRequest,
    user: AuthenticatedUser = Depends(get_current_hotel_user),
    use_case: PricingManagementUseCase = Depends(get_pricing_management_use_case),
) -> PricingPreviewResponse:
    try:
        return use_case.preview(user, payload)
    except PricingValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except PricingAuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except PricingTargetNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.post("/hotel/pricing/apply", response_model=PricingApplyResponse)
def apply_pricing_change(
    payload: PricingApplyRequest,
    user: AuthenticatedUser = Depends(get_current_hotel_user),
    use_case: PricingManagementUseCase = Depends(get_pricing_management_use_case),
) -> PricingApplyResponse:
    try:
        return use_case.apply(user, payload)
    except PricingValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except PricingAuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except PricingConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except PricingTargetNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.get("/hotel/pricing/history", response_model=list[PricingHistoryItem])
def list_pricing_history(
    user: AuthenticatedUser = Depends(get_current_hotel_user),
    use_case: PricingManagementUseCase = Depends(get_pricing_management_use_case),
) -> list[PricingHistoryItem]:
    return use_case.history(user)


@router.post("/hotel/pricing/history/{change_id}/revert", response_model=PricingRevertResponse)
def revert_pricing_change(
    change_id: UUID,
    user: AuthenticatedUser = Depends(get_current_hotel_user),
    use_case: PricingManagementUseCase = Depends(get_pricing_management_use_case),
) -> PricingRevertResponse:
    try:
        return use_case.revert(user, change_id)
    except PricingAuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except PricingConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except PricingTargetNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


def _validate_search_rules(query: SearchQuery) -> None:
    if query.check_out <= query.check_in:
        raise InvalidSearchRuleError(
            "check_out must be greater than check_in"
        )

    if (
        query.min_price is not None
        and query.max_price is not None
        and query.min_price > query.max_price
    ):
        raise InvalidSearchRuleError(
            "min_price cannot be greater than max_price"
        )

    valid_order_fields = {"price", "rating", "name"}
    if query.order_by.lower() not in valid_order_fields:
        raise InvalidSearchRuleError(
            "order_by must be one of: price, rating, name"
        )

    valid_order_direction = {"asc", "desc"}
    if query.order_dir.lower() not in valid_order_direction:
        raise InvalidSearchRuleError(
            "order_dir must be asc or desc"
        )


def _calculate_total_pages(total: int, page_size: int) -> int:
    if total == 0:
        return 0
    return (total + page_size - 1) // page_size


if settings.is_local_dev:

    @router.get("/test-dataset")
    def list_test_dataset(
        session: Session = Depends(get_session),
    ) -> dict:
        db_url = str(engine.url)
        enabled = db_url.startswith("sqlite") or db_url.startswith("postgresql")
        if not enabled:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Endpoint available only for local development test data",
            )

        properties = session.exec(select(Property)).all()
        room_types = session.exec(select(RoomType)).all()
        rate_plans = session.exec(select(RatePlan)).all()
        inventory_calendar = session.exec(select(InventoryCalendar)).all()
        rate_calendar = session.exec(select(RateCalendar)).all()
        amenities = session.exec(select(Amenity)).all()
        services = session.exec(select(Service)).all()
        property_amenity = session.exec(select(PropertyAmenity)).all()

        return {
            "counts": {
                "properties": len(properties),
                "room_types": len(room_types),
                "rate_plans": len(rate_plans),
                "inventory_calendar": len(inventory_calendar),
                "rate_calendar": len(rate_calendar),
                "amenities": len(amenities),
                "services": len(services),
                "property_amenity": len(property_amenity),
            },
            "properties": [
                {
                    "id": str(p.id),
                    "name": p.name,
                    "city": p.city,
                    "country": p.country,
                    "max_capacity": p.max_capacity,
                    "main_image_url": p.main_image_url,
                    "rating": p.rating,
                }
                for p in properties
            ],
        }
