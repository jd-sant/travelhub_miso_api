from datetime import date
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from assembly import (
    get_property_availability_use_case,
    get_search_properties_use_case,
)
from domain.schemas import (
    EmptyStateSuggestion,
    PropertyAvailabilityQuery,
    PropertyAvailabilityResponse,
    SearchPagination,
    SearchQuery,
    SearchResponse,
)
from domain.use_cases.check_property_availability import (
    CheckPropertyAvailabilityUseCase,
)
from domain.use_cases.search_properties import SearchPropertiesUseCase
from errors import (
    InvalidSearchRuleError,
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
        503: {"description": "Upstream service unavailable"},
    },
)
def search_properties(
    city: str | None = Query(default=None, min_length=2, max_length=120),
    check_in: date | None = Query(default=None),
    check_out: date | None = Query(default=None),
    guests: int = Query(ge=1),
    amenities: list[str] = Query(default_factory=list),
    min_price: Decimal | None = Query(default=None, ge=0),
    max_price: Decimal | None = Query(default=None, ge=0),
    min_lat: float | None = Query(default=None, ge=-90, le=90),
    max_lat: float | None = Query(default=None, ge=-90, le=90),
    min_lng: float | None = Query(default=None, ge=-180, le=180),
    max_lng: float | None = Query(default=None, ge=-180, le=180),
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
            min_lat=min_lat,
            max_lat=max_lat,
            min_lng=min_lng,
            max_lng=max_lng,
            order_by=order_by,
            order_dir=order_dir,
            page=page,
            page_size=page_size,
        )
        _validate_search_rules(query)
        result = use_case.execute(query)
    except InvalidSearchRuleError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except (PropertiesServiceUnavailableError, ReservationsServiceUnavailableError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        )

    total_pages = _calculate_total_pages(result.total, result.page_size)
    empty_state = []
    used_bbox = query.min_lat is not None
    if not result.items:
        if result.total == 0:
            if used_bbox:
                empty_state.append(
                    EmptyStateSuggestion(
                        code="TRY_OTHER_AREA",
                        message=(
                            "No encontramos resultados en esta zona. "
                            "Mueve el mapa para explorar otras áreas."
                        ),
                    )
                )
            else:
                empty_state.append(
                    EmptyStateSuggestion(
                        code="TRY_OTHER_CITY",
                        message=(
                            "No encontramos resultados en esa ciudad. "
                            "Intenta otra ciudad cercana."
                        ),
                    )
                )
        else:
            empty_state.append(
                EmptyStateSuggestion(
                    code="TRY_OTHER_DATES",
                    message=(
                        "Las propiedades disponibles no tienen fechas libres. "
                        "Prueba con fechas diferentes."
                    ),
                )
            )

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


@router.get(
    "/properties/{property_id}/availability",
    response_model=PropertyAvailabilityResponse,
    responses={503: {"description": "Upstream service unavailable"}},
)
def check_property_availability(
    property_id: UUID,
    check_in: date = Query(),
    check_out: date = Query(),
    guests: int = Query(ge=1),
    use_case: CheckPropertyAvailabilityUseCase = Depends(
        get_property_availability_use_case
    ),
) -> PropertyAvailabilityResponse:
    try:
        if check_out <= check_in:
            raise InvalidSearchRuleError("check_out must be greater than check_in")
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
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        )


def _validate_search_rules(query: SearchQuery) -> None:
    bbox_values = (query.min_lat, query.max_lat, query.min_lng, query.max_lng)
    bbox_provided = sum(v is not None for v in bbox_values)
    if 0 < bbox_provided < 4:
        raise InvalidSearchRuleError(
            "bbox requires all four of min_lat, max_lat, min_lng, max_lng"
        )
    has_bbox = bbox_provided == 4
    if has_bbox:
        if query.min_lat >= query.max_lat:
            raise InvalidSearchRuleError("min_lat must be less than max_lat")
        if query.min_lng >= query.max_lng:
            raise InvalidSearchRuleError("min_lng must be less than max_lng")

    if not has_bbox and not query.city:
        raise InvalidSearchRuleError(
            "city is required when bbox is not provided"
        )

    if query.check_in is None and query.check_out is None:
        pass
    elif query.check_in is None or query.check_out is None:
        raise InvalidSearchRuleError(
            "check_in and check_out must be provided together"
        )
    elif query.check_out <= query.check_in:
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
