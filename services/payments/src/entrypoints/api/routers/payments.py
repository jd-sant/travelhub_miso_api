from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status

from assembly import (
    get_create_payment_checkout_session_use_case,
    get_create_payment_charge_use_case,
    get_create_payment_refund_use_case,
    get_finalize_stripe_payment_use_case,
    get_get_payment_confirmation_summary_use_case,
    get_get_payment_use_case,
    get_get_payment_checkout_session_use_case,
    get_get_payment_refund_use_case,
    get_handle_stripe_webhook_use_case,
    get_list_payment_events_use_case,
)
from core.config import settings
from domain.schemas.checkout import (
    PaymentCheckoutSessionRequest,
    PaymentCheckoutSessionResponse,
    PaymentCheckoutStatusResponse,
    PaymentConfirmationSummaryResponse,
    PaymentFinalizeRequest,
    PaymentFinalizeResponse,
    PaymentsConfigResponse,
)
from domain.schemas.payment import (
    PaymentChargeRequest,
    PaymentEventResponse,
    PaymentPublicResponse,
    PaymentRefundCreateRequest,
    PaymentRefundPublicResponse,
)
from domain.use_cases.create_payment_checkout_session import CreatePaymentCheckoutSessionUseCase
from domain.use_cases.create_payment_charge import CreatePaymentChargeUseCase
from domain.use_cases.create_payment_refund import CreatePaymentRefundUseCase
from domain.use_cases.finalize_stripe_payment import FinalizeStripePaymentUseCase
from domain.use_cases.get_payment_confirmation_summary import GetPaymentConfirmationSummaryUseCase
from domain.use_cases.get_payment import GetPaymentUseCase
from domain.use_cases.get_payment_checkout_session import GetPaymentCheckoutSessionUseCase
from domain.use_cases.get_payment_refund import GetPaymentRefundUseCase
from domain.use_cases.handle_stripe_webhook import HandleStripeWebhookUseCase
from domain.use_cases.list_payment_events import ListPaymentEventsUseCase
from errors import (
    DuplicatePaymentError,
    InsecureTransportError,
    InvalidRefundAmountError,
    InvalidChecksumError,
    PaymentCheckoutSessionNotFoundError,
    PaymentNotFoundError,
    PaymentRefundNotAllowedError,
    PaymentRefundNotFoundError,
    StripeConfigurationError,
    StripeWebhookVerificationError,
    UnsupportedPaymentOperationError,
)

router = APIRouter(prefix="/payments", tags=["payments"])


def _assert_secure_transport(x_forwarded_proto: str | None) -> None:
    if settings.enforce_tls_header and x_forwarded_proto != "https":
        raise InsecureTransportError("TLS 1.2+ is required for payment requests")


def _resolve_source_ip(
    request: Request | None,
    x_forwarded_for: str | None,
) -> str | None:
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    if request and request.client:
        return request.client.host
    return None


@router.get("/config", response_model=PaymentsConfigResponse, status_code=status.HTTP_200_OK)
def get_payments_config() -> PaymentsConfigResponse:
    return PaymentsConfigResponse(
        provider=settings.payment_provider,
        stripe_enabled=settings.stripe_enabled,
        publishable_key=settings.stripe_publishable_key,
    )


@router.post(
    "/create-intent",
    response_model=PaymentCheckoutSessionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_checkout_session(
    request: Request,
    payload: PaymentCheckoutSessionRequest,
    x_forwarded_proto: str | None = Header(default=None),
    x_forwarded_for: str | None = Header(default=None),
    use_case: CreatePaymentCheckoutSessionUseCase = Depends(get_create_payment_checkout_session_use_case),
) -> PaymentCheckoutSessionResponse:
    try:
        _assert_secure_transport(x_forwarded_proto)
        return use_case.execute(payload, source_ip=_resolve_source_ip(request, x_forwarded_for))
    except InsecureTransportError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/finalize", response_model=PaymentFinalizeResponse, status_code=status.HTTP_200_OK)
def finalize_stripe_payment(
    request: Request,
    payload: PaymentFinalizeRequest,
    x_forwarded_proto: str | None = Header(default=None),
    x_forwarded_for: str | None = Header(default=None),
    use_case: FinalizeStripePaymentUseCase = Depends(get_finalize_stripe_payment_use_case),
) -> PaymentFinalizeResponse:
    try:
        _assert_secure_transport(x_forwarded_proto)
        return use_case.execute(payload, source_ip=_resolve_source_ip(request, x_forwarded_for))
    except InsecureTransportError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except PaymentCheckoutSessionNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sesión de pago no encontrada.")
    except StripeConfigurationError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))


@router.get(
    "/checkout/{payment_transaction_id}",
    response_model=PaymentCheckoutStatusResponse,
    status_code=status.HTTP_200_OK,
)
def get_checkout_session_status(
    payment_transaction_id: UUID,
    use_case: GetPaymentCheckoutSessionUseCase = Depends(get_get_payment_checkout_session_use_case),
) -> PaymentCheckoutStatusResponse:
    try:
        return use_case.execute(payment_transaction_id)
    except PaymentCheckoutSessionNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sesión de pago no encontrada.")


@router.post("/webhook", status_code=status.HTTP_200_OK)
async def stripe_webhook(
    request: Request,
    stripe_signature: str | None = Header(default=None, alias="Stripe-Signature"),
    x_forwarded_for: str | None = Header(default=None),
    use_case: HandleStripeWebhookUseCase = Depends(get_handle_stripe_webhook_use_case),
) -> Response:
    try:
        payload = await request.body()
        use_case.execute((payload, stripe_signature or ""), source_ip=_resolve_source_ip(request, x_forwarded_for))
        return Response(status_code=status.HTTP_200_OK)
    except StripeWebhookVerificationError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Firma de webhook inválida.")


@router.post("/charges", response_model=PaymentPublicResponse, status_code=status.HTTP_201_CREATED)
def create_charge(
    request: Request,
    payload: PaymentChargeRequest,
    x_forwarded_proto: str | None = Header(default=None),
    x_forwarded_for: str | None = Header(default=None),
    use_case: CreatePaymentChargeUseCase = Depends(get_create_payment_charge_use_case),
) -> PaymentPublicResponse:
    try:
        _assert_secure_transport(x_forwarded_proto)
        return use_case.execute(payload, source_ip=_resolve_source_ip(request, x_forwarded_for))
    except DuplicatePaymentError as exc:
        duplicate_window_seconds = settings.payment_duplicate_window_seconds
        message = (
            "Se reutilizó una idempotency_key ya registrada."
            if exc.reason == "idempotency_key_reused"
            else (
                "Se detectó una transacción duplicada en menos de "
                f"{duplicate_window_seconds} segundos."
            )
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": message,
                "duplicate_payment_id": str(exc.duplicate_payment_id),
            },
        )
    except InvalidChecksumError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Checksum de integridad inválido.",
        )
    except InsecureTransportError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    except UnsupportedPaymentOperationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )


@router.post("/refunds", response_model=PaymentRefundPublicResponse, status_code=status.HTTP_201_CREATED)
def create_payment_refund(
    request: Request,
    payload: PaymentRefundCreateRequest,
    x_forwarded_proto: str | None = Header(default=None),
    x_forwarded_for: str | None = Header(default=None),
    use_case: CreatePaymentRefundUseCase = Depends(get_create_payment_refund_use_case),
) -> PaymentRefundPublicResponse:
    try:
        _assert_secure_transport(x_forwarded_proto)
        return use_case.execute(payload, source_ip=_resolve_source_ip(request, x_forwarded_for))
    except InsecureTransportError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    except PaymentNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pago no encontrado.",
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


@router.get("/refunds/{refund_id}", response_model=PaymentRefundPublicResponse, status_code=status.HTTP_200_OK)
def get_payment_refund(
    refund_id: UUID,
    use_case: GetPaymentRefundUseCase = Depends(get_get_payment_refund_use_case),
) -> PaymentRefundPublicResponse:
    try:
        return use_case.execute(refund_id)
    except PaymentRefundNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reembolso no encontrado.",
        )


@router.get("/{payment_id}", response_model=PaymentPublicResponse, status_code=status.HTTP_200_OK)
def get_payment(
    payment_id: UUID,
    use_case: GetPaymentUseCase = Depends(get_get_payment_use_case),
) -> PaymentPublicResponse:
    try:
        return use_case.execute(payment_id)
    except PaymentNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pago no encontrado.",
        )


@router.get(
    "/{payment_id}/confirmation",
    response_model=PaymentConfirmationSummaryResponse,
    status_code=status.HTTP_200_OK,
)
def get_payment_confirmation(
    payment_id: UUID,
    use_case: GetPaymentConfirmationSummaryUseCase = Depends(
        get_get_payment_confirmation_summary_use_case
    ),
) -> PaymentConfirmationSummaryResponse:
    try:
        return use_case.execute(payment_id)
    except PaymentNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pago no encontrado.",
        )


@router.get("/{payment_id}/events", response_model=list[PaymentEventResponse], status_code=status.HTTP_200_OK)
def list_payment_events(
    payment_id: UUID,
    use_case: ListPaymentEventsUseCase = Depends(get_list_payment_events_use_case),
) -> list[PaymentEventResponse]:
    try:
        return use_case.execute(payment_id)
    except PaymentNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pago no encontrado.",
        )
