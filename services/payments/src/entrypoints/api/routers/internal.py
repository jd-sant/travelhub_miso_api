from fastapi import APIRouter, Depends, HTTPException, Request, status

from assembly import (
    get_payment_repository,
    get_process_queued_payments_use_case,
    get_retry_reservation_confirmations_use_case,
)
from core.config import settings
from domain.ports.payment_repository import PaymentRepository
from domain.schemas.payment import (
    PaymentByReservation,
    PaymentProcessingRetryResponse,
    PaymentsByReservationsRequest,
    PaymentsByReservationsResponse,
    ReservationConfirmationRetryResponse,
)
from domain.use_cases.process_queued_payments import ProcessQueuedPaymentsUseCase
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
    "/payment-processing/retry",
    response_model=PaymentProcessingRetryResponse,
    status_code=status.HTTP_200_OK,
)
def retry_payment_processing(
    request: Request,
    _: None = Depends(_verify_api_key),
    use_case: ProcessQueuedPaymentsUseCase = Depends(
        get_process_queued_payments_use_case
    ),
) -> PaymentProcessingRetryResponse:
    return use_case.execute(source_ip=_resolve_source_ip(request))


@router.post(
    "/payments/by-reservations",
    response_model=PaymentsByReservationsResponse,
    status_code=status.HTTP_200_OK,
)
def list_payments_by_reservations(
    payload: PaymentsByReservationsRequest,
    _: None = Depends(_verify_api_key),
    repository: PaymentRepository = Depends(get_payment_repository),
) -> PaymentsByReservationsResponse:
    items, currencies = repository.list_amounts_by_reservations(
        payload.reservation_ids,
        status=payload.status,
    )
    return PaymentsByReservationsResponse(
        items=[
            PaymentByReservation(
                reservation_id=res_id,
                amount_in_cents=amount,
                currency=cur,
            )
            for (res_id, amount, cur) in items
        ],
        available_currencies=currencies,
    )
