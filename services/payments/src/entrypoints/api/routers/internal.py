from hmac import compare_digest

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status

from assembly import (
    get_create_additional_charge_for_reservation_use_case,
    get_create_refund_for_reservation_use_case,
    get_retry_payment_refunds_use_case,
    get_retry_reservation_confirmations_use_case,
)
from core.config import settings
from core.telemetry import resolve_correlation_id
from domain.schemas.payment import (
    AdditionalChargeRequest,
    PaymentPublicResponse,
    PaymentRefundPublicResponse,
    PaymentRefundRetryResponse,
    ReservationConfirmationRetryResponse,
    ReservationRefundRequest,
)
from domain.use_cases.create_additional_charge_for_reservation import (
    CreateAdditionalChargeForReservationUseCase,
)
from domain.use_cases.create_refund_for_reservation import (
    CreateRefundForReservationUseCase,
)
from domain.use_cases.retry_payment_refunds import RetryPaymentRefundsUseCase
from domain.use_cases.retry_reservation_confirmations import RetryReservationConfirmationsUseCase
from errors import InvalidRefundAmountError, PaymentNotFoundError, PaymentRefundNotAllowedError

router = APIRouter(prefix="/internal", tags=["internal"])


def _verify_api_key(request: Request) -> None:
    api_key = request.headers.get("X-Internal-Api-Key")
    if not api_key or not compare_digest(api_key.strip(), settings.internal_api_key):
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
    correlation_id: str = Depends(resolve_correlation_id),
    _: None = Depends(_verify_api_key),
    use_case: RetryPaymentRefundsUseCase = Depends(get_retry_payment_refunds_use_case),
) -> PaymentRefundRetryResponse:
    return use_case.execute(
        source_ip=_resolve_source_ip(request),
        correlation_id=correlation_id,
    )


@router.post(
    "/payments/refunds",
    response_model=PaymentRefundPublicResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_refund_for_reservation(
    request: Request,
    payload: ReservationRefundRequest,
    correlation_id: str = Depends(resolve_correlation_id),
    _: None = Depends(_verify_api_key),
    use_case: CreateRefundForReservationUseCase = Depends(
        get_create_refund_for_reservation_use_case
    ),
) -> PaymentRefundPublicResponse:
    try:
        return use_case.execute(
            payload,
            source_ip=_resolve_source_ip(request),
            correlation_id=correlation_id,
        )
    except PaymentNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No se encontro un pago confirmado para la reserva.",
        )
    except PaymentRefundNotAllowedError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Solo se permiten reembolsos para pagos confirmados.",
        )
    except InvalidRefundAmountError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El monto del reembolso supera el monto del pago original.",
        )


@router.post(
    "/payments/additional-charges",
    response_model=PaymentPublicResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_additional_charge_for_reservation(
    request: Request,
    payload: AdditionalChargeRequest,
    _: None = Depends(_verify_api_key),
    use_case: CreateAdditionalChargeForReservationUseCase = Depends(
        get_create_additional_charge_for_reservation_use_case
    ),
) -> PaymentPublicResponse:
    return use_case.execute(payload, source_ip=_resolve_source_ip(request))
