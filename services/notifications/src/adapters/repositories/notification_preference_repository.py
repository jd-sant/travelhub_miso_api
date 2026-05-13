from datetime import datetime, timezone
from uuid import UUID

from sqlmodel import Session, select

from adapters.models.notification_preference import NotificationPreference
from domain.ports.notification_preference_repository import (
    NotificationPreferenceRecord,
    NotificationPreferenceRepository,
)


class SQLModelNotificationPreferenceRepository(NotificationPreferenceRepository):
    def __init__(self, session: Session):
        self.session = session

    def get(self, user_id: UUID) -> NotificationPreferenceRecord:
        row = self.session.exec(
            select(NotificationPreference).where(
                NotificationPreference.user_id == user_id
            )
        ).first()
        if row is None:
            return NotificationPreferenceRecord(user_id=user_id)
        return NotificationPreferenceRecord(
            user_id=row.user_id,
            status_changes_enabled=row.status_changes_enabled,
            arrival_reminders_enabled=row.arrival_reminders_enabled,
        )

    def upsert(
        self,
        *,
        user_id: UUID,
        status_changes_enabled: bool | None = None,
        arrival_reminders_enabled: bool | None = None,
    ) -> NotificationPreferenceRecord:
        row = self.session.exec(
            select(NotificationPreference).where(
                NotificationPreference.user_id == user_id
            )
        ).first()
        if row is None:
            row = NotificationPreference(user_id=user_id)
        if status_changes_enabled is not None:
            row.status_changes_enabled = status_changes_enabled
        if arrival_reminders_enabled is not None:
            row.arrival_reminders_enabled = arrival_reminders_enabled
        row.updated_at = datetime.now(timezone.utc)
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return NotificationPreferenceRecord(
            user_id=row.user_id,
            status_changes_enabled=row.status_changes_enabled,
            arrival_reminders_enabled=row.arrival_reminders_enabled,
        )
