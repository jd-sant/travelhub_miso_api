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
    city: str = Query(min_length=2, max_length=120),
    check_in: date = Query(),
    check_out: date = Query(),
    guests: int = Query(ge=1),
    amenities: list[str] = Query(default_factory=list),
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
    except InvalidSearchRuleError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except (PropertiesServiceUnavailableError, ReservationsServiceUnavailableError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        )

    total_pages = _calculate_total_pages(result.total, result.page_size)
    empty_state = []
    if not result.items:
        if result.total == 0:
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
