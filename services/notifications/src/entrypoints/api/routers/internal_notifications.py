from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, status

from assembly import (
    get_create_payment_confirmation_use_case,
    get_notification_delivery_runner,
)
from core.config import settings
from domain.ports.notification_delivery_runner import NotificationDeliveryRunner
from domain.schemas.notification import (
    NotificationResponse,
    NotificationStatus,
    PaymentConfirmationRequest,
)
from domain.use_cases.create_payment_confirmation import CreatePaymentConfirmationUseCase
from errors import (
    InvalidPaymentConfirmationError,
    PaymentConfirmationUnavailableError,
    TravelerProfileNotFoundError,
)

router = APIRouter(prefix="/internal", tags=["internal"])


@router.post(
    "/payment-confirmations",
    response_model=NotificationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_payment_confirmation(
    payload: PaymentConfirmationRequest,
    background_tasks: BackgroundTasks,
    x_internal_api_key: str | None = Header(default=None),
    use_case: CreatePaymentConfirmationUseCase = Depends(get_create_payment_confirmation_use_case),
    delivery_runner: NotificationDeliveryRunner = Depends(get_notification_delivery_runner),
) -> NotificationResponse:
    if x_internal_api_key != settings.internal_api_key:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    try:
        notification = use_case.execute(payload)
        if notification.status != NotificationStatus.sent:
            background_tasks.add_task(
                delivery_runner.run_delivery,
                notification_id=notification.notification_id,
                source_ip=payload.source_ip,
            )
        return notification
    except InvalidPaymentConfirmationError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except TravelerProfileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except PaymentConfirmationUnavailableError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
