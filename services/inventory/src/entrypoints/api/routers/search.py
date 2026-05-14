from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session, select

from assembly import (
    get_property_availability_use_case,
    get_pricing_management_use_case,
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
from domain.schemas import PropertyAvailabilityQuery, PropertyAvailabilityResponse
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
)
from errors import (
    InvalidSearchRuleError,
    PricingAuthorizationError,
    PricingConflictError,
    PricingServiceUnavailableError,
    PricingTargetNotFoundError,
    PricingValidationError,
)

router = APIRouter(prefix="/inventory", tags=["inventory"])


@router.get("/status")
def inventory_status() -> dict[str, str]:
    return {"service": "inventory", "status": "ok"}


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


@router.get("/hotel/pricing/targets", response_model=list[PricingTargetOption])
def list_pricing_targets(
    user: AuthenticatedUser = Depends(get_current_hotel_user),
    use_case: PricingManagementUseCase = Depends(get_pricing_management_use_case),
) -> list[PricingTargetOption]:
    try:
        return use_case.list_targets(user)
    except PricingAuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except PricingServiceUnavailableError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))


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
    except PricingServiceUnavailableError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
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
    except PricingServiceUnavailableError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
    except PricingConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except PricingTargetNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.get("/hotel/pricing/history", response_model=list[PricingHistoryItem])
def list_pricing_history(
    user: AuthenticatedUser = Depends(get_current_hotel_user),
    use_case: PricingManagementUseCase = Depends(get_pricing_management_use_case),
) -> list[PricingHistoryItem]:
    try:
        return use_case.history(user)
    except PricingAuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except PricingServiceUnavailableError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))


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
    except PricingServiceUnavailableError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
    except PricingConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except PricingTargetNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


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
