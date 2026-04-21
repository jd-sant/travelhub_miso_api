import asyncio
import json
from uuid import UUID

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    Header,
    HTTPException,
    Request,
    Response,
    status,
)
from fastapi.responses import StreamingResponse

from assembly import (
    get_create_payment_checkout_session_use_case,
    get_create_payment_charge_use_case,
    get_finalize_stripe_payment_use_case,
    get_get_payment_confirmation_summary_use_case,
    get_get_payment_use_case,
    get_get_payment_checkout_session_use_case,
    get_handle_stripe_webhook_use_case,
    get_list_payment_events_use_case,
    get_payment_processing_runner,
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
    PaymentStatus,
)
from domain.ports.payment_processing_runner import PaymentProcessingRunner
from domain.use_cases.create_payment_checkout_session import CreatePaymentCheckoutSessionUseCase
from domain.use_cases.create_payment_charge import CreatePaymentChargeUseCase
from domain.use_cases.finalize_stripe_payment import FinalizeStripePaymentUseCase
from domain.use_cases.get_payment_confirmation_summary import GetPaymentConfirmationSummaryUseCase
from domain.use_cases.get_payment import GetPaymentUseCase
from domain.use_cases.get_payment_checkout_session import GetPaymentCheckoutSessionUseCase
from domain.use_cases.handle_stripe_webhook import HandleStripeWebhookUseCase
from domain.use_cases.list_payment_events import ListPaymentEventsUseCase
from errors import (
    DuplicatePaymentError,
    InsecureTransportError,
    InvalidChecksumError,
    PaymentCheckoutSessionNotFoundError,
    PaymentNotFoundError,
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


@router.post(
    "/finalize",
    response_model=PaymentFinalizeResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def finalize_stripe_payment(
    background_tasks: BackgroundTasks,
    request: Request,
    payload: PaymentFinalizeRequest,
    x_forwarded_proto: str | None = Header(default=None),
    x_forwarded_for: str | None = Header(default=None),
    use_case: FinalizeStripePaymentUseCase = Depends(get_finalize_stripe_payment_use_case),
    runner: PaymentProcessingRunner = Depends(get_payment_processing_runner),
) -> PaymentFinalizeResponse:
    try:
        _assert_secure_transport(x_forwarded_proto)
        source_ip = _resolve_source_ip(request, x_forwarded_for)
        response = use_case.execute(payload, source_ip=source_ip)
        if response.status == "pending":
            background_tasks.add_task(
                runner.run_checkout_processing,
                payment_transaction_id=payload.payment_transaction_id,
                source_ip=source_ip,
            )
        return response
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


@router.get("/{payment_id}/stream", status_code=status.HTTP_200_OK)
async def stream_payment_status(
    request: Request,
    payment_id: UUID,
    get_payment_use_case: GetPaymentUseCase = Depends(get_get_payment_use_case),
    list_events_use_case: ListPaymentEventsUseCase = Depends(get_list_payment_events_use_case),
) -> StreamingResponse:
    try:
        get_payment_use_case.execute(payment_id)
    except PaymentNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pago no encontrado.",
        )

    async def event_stream():
        last_status: str | None = None
        last_failure_reason: str | None = None
        last_event_created_at = None
        last_event_id: UUID | None = None
        while True:
            if await request.is_disconnected():
                break

            payment = get_payment_use_case.execute(payment_id)
            events = list_events_use_case.execute(
                payment_id,
                after_created_at=last_event_created_at,
                after_event_id=last_event_id,
            )

            for event in events:
                yield (
                    "event: payment_event\n"
                    f"data: {json.dumps({'event_id': str(event.event_id), 'event_type': event.event_type, 'payload': event.payload, 'created_at': event.created_at.isoformat()})}\n\n"
                )
                last_event_created_at = event.created_at
                last_event_id = event.event_id

            current_status = payment.status.value
            if (
                current_status != last_status
                or payment.failure_reason != last_failure_reason
            ):
                yield (
                    "event: payment_status\n"
                    f"data: {json.dumps({'payment_id': str(payment.payment_id), 'status': current_status, 'failure_reason': payment.failure_reason, 'receipt_id': str(payment.receipt_id) if payment.receipt_id else None, 'receipt_number': payment.receipt_number})}\n\n"
                )
                last_status = current_status
                last_failure_reason = payment.failure_reason

            if payment.status in {PaymentStatus.confirmed, PaymentStatus.failed}:
                break

            await asyncio.sleep(1)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
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
