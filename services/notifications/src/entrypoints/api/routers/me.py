from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session, desc, select

from adapters.auth.jwt_auth import current_user
from adapters.models.notification_audit_log import NotificationAuditLog
from assembly import (
    get_device_token_repository,
    get_notification_preference_repository,
)
from db.session import get_session
from domain.ports.device_token_repository import DeviceTokenRepository
from domain.ports.notification_preference_repository import (
    NotificationPreferenceRepository,
)
from entrypoints.api.schemas.me import (
    DeviceRegistrationRequest,
    NotificationListItem,
    NotificationListResponse,
    NotificationPreferenceResponse,
    NotificationPreferenceUpdateRequest,
)

router = APIRouter(prefix="/me", tags=["me"])


@router.post("/devices", status_code=status.HTTP_201_CREATED)
def register_device(
    payload: DeviceRegistrationRequest,
    user_id: UUID = Depends(current_user),
    repo: DeviceTokenRepository = Depends(get_device_token_repository),
) -> dict:
    repo.upsert(
        user_id=user_id,
        token=payload.token,
        platform=payload.platform,
        app_version=payload.app_version,
    )
    return {"status": "registered"}


@router.delete("/devices/{token}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_device(
    token: str,
    user_id: UUID = Depends(current_user),
    repo: DeviceTokenRepository = Depends(get_device_token_repository),
) -> None:
    repo.revoke(user_id=user_id, token=token)


@router.get("/notification-preferences", response_model=NotificationPreferenceResponse)
def get_preferences(
    user_id: UUID = Depends(current_user),
    repo: NotificationPreferenceRepository = Depends(get_notification_preference_repository),
) -> NotificationPreferenceResponse:
    record = repo.get(user_id)
    return NotificationPreferenceResponse(
        status_changes_enabled=record.status_changes_enabled,
        arrival_reminders_enabled=record.arrival_reminders_enabled,
    )


@router.patch("/notification-preferences", response_model=NotificationPreferenceResponse)
def update_preferences(
    payload: NotificationPreferenceUpdateRequest,
    user_id: UUID = Depends(current_user),
    repo: NotificationPreferenceRepository = Depends(get_notification_preference_repository),
) -> NotificationPreferenceResponse:
    updated = repo.upsert(
        user_id=user_id,
        status_changes_enabled=payload.status_changes_enabled,
        arrival_reminders_enabled=payload.arrival_reminders_enabled,
    )
    return NotificationPreferenceResponse(
        status_changes_enabled=updated.status_changes_enabled,
        arrival_reminders_enabled=updated.arrival_reminders_enabled,
    )


@router.get("/notifications", response_model=NotificationListResponse)
def list_notifications(
    user_id: UUID = Depends(current_user),
    filter: str = Query("all", pattern="^(all|unread)$"),
    limit: int = Query(50, ge=1, le=100),
    session: Session = Depends(get_session),
) -> NotificationListResponse:
    stmt = select(NotificationAuditLog).where(
        NotificationAuditLog.traveler_id == user_id,
        NotificationAuditLog.channel == "push",
        NotificationAuditLog.delivery_status.in_(["sent", "opened"]),
    )
    if filter == "unread":
        stmt = stmt.where(NotificationAuditLog.opened_at.is_(None))
    stmt = stmt.order_by(desc(NotificationAuditLog.created_at)).limit(limit)
    rows = session.exec(stmt).all()

    items: list[NotificationListItem] = []
    for r in rows:
        payload = r.payload or {}
        title = payload.get("title") or _action_to_title(r.action)
        body = payload.get("message") or payload.get("body") or ""
        items.append(
            NotificationListItem(
                id=r.id,
                notification_id=r.notification_id,
                title=title,
                body=body,
                entity_type=r.entity_type,
                entity_id=r.entity_id,
                delivery_status=r.delivery_status,
                created_at=r.created_at,
                is_read=r.opened_at is not None,
            )
        )
    return NotificationListResponse(items=items)


@router.post(
    "/notifications/{audit_id}/opened",
    status_code=status.HTTP_200_OK,
)
def mark_opened(
    audit_id: UUID,
    user_id: UUID = Depends(current_user),
    session: Session = Depends(get_session),
) -> dict:
    row = session.exec(
        select(NotificationAuditLog).where(
            NotificationAuditLog.id == audit_id,
            NotificationAuditLog.traveler_id == user_id,
        )
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Notificación no encontrada")
    if row.opened_at is None:
        row.opened_at = datetime.now(timezone.utc)
        row.delivery_status = "opened"
        session.add(row)
        session.commit()
    return {"status": "opened", "opened_at": row.opened_at}


def _action_to_title(action: str) -> str:
    if "booking_confirmed" in action:
        return "Reserva confirmada"
    if "modification_confirmed" in action:
        return "Reserva modificada"
    if "cancellation_confirmed" in action:
        return "Reserva cancelada"
    if "checkin_registered" in action:
        return "Check-in registrado"
    if "checkout_registered" in action:
        return "Check-out registrado"
    if "arrival_reminder" in action:
        return "Recordatorio de Check-in"
    if "refund" in action:
        return "Actualización de reembolso"
    return "TravelHub"
