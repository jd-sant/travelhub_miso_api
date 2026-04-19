from fastapi import APIRouter, Depends, Header, HTTPException, Request, status

from assembly import (
    get_retry_payment_refunds_use_case,
    get_retry_reservation_confirmations_use_case,
)
from core.config import settings
from domain.schemas.payment import PaymentRefundRetryResponse, ReservationConfirmationRetryResponse
from domain.use_cases.retry_payment_refunds import RetryPaymentRefundsUseCase
from domain.use_cases.retry_reservation_confirmations import RetryReservationConfirmationsUseCase

router = APIRouter(prefix="/internal", tags=["internal"])


def _verify_api_key(request: Request) -> None:
    api_key = request.headers.get("X-Internal-Api-Key")
    if not api_key or api_key != settings.internal_api_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden",
        )


def _resolve_source_ip(request: Request) -> str | None:
    if request.client:
        return request.client.host
    return None


@router.post(
    "/reservation-confirmations/retry",
    response_model=ReservationConfirmationRetryResponse,
    status_code=status.HTTP_200_OK,
)
def retry_reservation_confirmations(
    request: Request,
    _: None = Depends(_verify_api_key),
    use_case: RetryReservationConfirmationsUseCase = Depends(
        get_retry_reservation_confirmations_use_case
    ),
) -> ReservationConfirmationRetryResponse:
    return use_case.execute(source_ip=_resolve_source_ip(request))


@router.post(
    "/payments/refunds/retry",
    response_model=PaymentRefundRetryResponse,
    status_code=status.HTTP_200_OK,
)
def retry_payment_refunds(
    request: Request,
    _: None = Depends(_verify_api_key),
    use_case: RetryPaymentRefundsUseCase = Depends(get_retry_payment_refunds_use_case),
) -> PaymentRefundRetryResponse:
    return use_case.execute(source_ip=_resolve_source_ip(request))
