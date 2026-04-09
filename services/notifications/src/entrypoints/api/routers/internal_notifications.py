from fastapi import APIRouter, Depends, Header, HTTPException, status

from core.config import settings
from assembly import get_create_payment_confirmation_use_case
from domain.schemas.notification import NotificationResponse, PaymentConfirmationRequest
from domain.use_cases.create_payment_confirmation import CreatePaymentConfirmationUseCase

router = APIRouter(prefix="/internal", tags=["internal"])


@router.post(
    "/payment-confirmations",
    response_model=NotificationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_payment_confirmation(
    payload: PaymentConfirmationRequest,
    x_internal_api_key: str | None = Header(default=None),
    use_case: CreatePaymentConfirmationUseCase = Depends(get_create_payment_confirmation_use_case),
) -> NotificationResponse:
    if x_internal_api_key != settings.internal_api_key:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    return use_case.execute(payload)
