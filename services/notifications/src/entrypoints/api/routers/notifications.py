from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, status

from assembly import get_get_notification_use_case
from core.config import settings
from domain.schemas.notification import NotificationResponse
from domain.use_cases.get_notification import GetNotificationUseCase
from errors import NotificationNotFoundError

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("/{notification_id}", response_model=NotificationResponse, status_code=status.HTTP_200_OK)
def get_notification(
    notification_id: UUID,
    x_internal_api_key: str | None = Header(default=None),
    use_case: GetNotificationUseCase = Depends(get_get_notification_use_case),
) -> NotificationResponse:
    if x_internal_api_key != settings.internal_api_key:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    try:
        return use_case.execute(notification_id)
    except NotificationNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notificacion no encontrada.")
