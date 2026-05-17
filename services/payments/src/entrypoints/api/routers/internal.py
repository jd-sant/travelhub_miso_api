from hmac import compare_digest

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status

from assembly import (
    get_create_reservation_refund_use_case,
    get_payment_repository,
    get_process_queued_payments_use_case,
    get_retry_reservation_confirmations_use_case,
    get_create_additional_charge_for_reservation_use_case,
    get_create_refund_for_reservation_use_case,
    get_reservation_updater,
    get_retry_payment_refunds_use_case
)
from core.config import settings
from core.telemetry import resolve_correlation_id
from domain.ports.notification_dispatcher import ReservationUpdater
from domain.ports.payment_repository import PaymentRepository
from domain.schemas.payment import (
    AdditionalChargeRequest,
    PaymentByReservation,
    PaymentProcessingRetryResponse,
    PaymentPublicResponse,
    PaymentRefundPublicResponse,
    PaymentRefundRetryResponse,
    PaymentsByReservationsRequest,
    PaymentsByReservationsResponse,
    ReservationConfirmationRetryResponse,
    ReservationPaymentRefundRequest,
    ReservationRefundRequest,
    ReservationRefundResponse,
)
from domain.use_cases.create_reservation_refund import CreateReservationRefundUseCase
from domain.use_cases.process_queued_payments import ProcessQueuedPaymentsUseCase
from domain.use_cases.create_additional_charge_for_reservation import (
    CreateAdditionalChargeForReservationUseCase,
)
from domain.use_cases.create_refund_for_reservation import (
    CreateRefundForReservationUseCase,
)
from domain.use_cases.retry_payment_refunds import RetryPaymentRefundsUseCase
from domain.use_cases.retry_reservation_confirmations import RetryReservationConfirmationsUseCase
from errors import InvalidRefundAmountError, PaymentNotFoundError, PaymentRefundNotAllowedError
from errors import PaymentNotFoundError, RefundNotAvailableError

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


@router.post(
    "/refunds",
    response_model=ReservationRefundResponse,
    status_code=status.HTTP_200_OK,
)
def create_reservation_refund(
    request: Request,
    payload: ReservationRefundRequest,
    _: None = Depends(_verify_api_key),
    use_case: CreateReservationRefundUseCase = Depends(
        get_create_reservation_refund_use_case
    ),
) -> ReservationRefundResponse:
    try:
        return use_case.execute(
            payload.model_copy(
                update={"source_ip": payload.source_ip or _resolve_source_ip(request)}
            )
        )
    except PaymentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except RefundNotAvailableError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


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
    payload: ReservationPaymentRefundRequest,
    correlation_id: str = Depends(resolve_correlation_id),
    _: None = Depends(_verify_api_key),
    use_case: CreateRefundForReservationUseCase = Depends(
        get_create_refund_for_reservation_use_case
    ),
    reservation_updater: ReservationUpdater = Depends(get_reservation_updater),
) -> PaymentRefundPublicResponse:
    try:
        refund = use_case.execute(
            payload,
            source_ip=_resolve_source_ip(request),
            correlation_id=correlation_id,
        )

        if settings.app_env in ("development", "dev", "test"):
            reservation_updater.notify_refund_result(
                reservation_id=refund.reservation_id,
                status="succeeded",
                amount_in_cents=refund.amount_in_cents,
                refund_id=refund.refund_id,
                source_ip=_resolve_source_ip(request),
            )

        return refund
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
