from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, status

from assembly import get_property_cancellation_policy_use_case
from core.config import settings
from domain.schemas.property_policy import PropertyCancellationPolicyResponse
from domain.use_cases.get_property_cancellation_policy import (
    GetPropertyCancellationPolicyUseCase,
)
from errors import PropertyNotFoundError

router = APIRouter(prefix="/internal", tags=["internal"])


def _verify_api_key(x_internal_api_key: str = Header(default=None)) -> None:
    if x_internal_api_key != settings.internal_api_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden",
        )


@router.get(
    "/properties/{property_id}/cancellation-policy",
    response_model=PropertyCancellationPolicyResponse,
    status_code=status.HTTP_200_OK,
)
def get_cancellation_policy(
    property_id: UUID,
    _: None = Depends(_verify_api_key),
    use_case: GetPropertyCancellationPolicyUseCase = Depends(
        get_property_cancellation_policy_use_case
    ),
) -> PropertyCancellationPolicyResponse:
    try:
        return use_case.execute(property_id)
    except PropertyNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cancellation policy for property {property_id} not found",
        )
