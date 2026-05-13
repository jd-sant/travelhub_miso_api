from datetime import datetime, timezone
from uuid import UUID

from sqlmodel import Session, select

from adapters.models.device_token import DeviceToken
from domain.ports.device_token_repository import (
    DeviceTokenRecord,
    DeviceTokenRepository,
)


class SQLModelDeviceTokenRepository(DeviceTokenRepository):
    def __init__(self, session: Session):
        self.session = session

    def upsert(
        self,
        *,
        user_id: UUID,
        token: str,
        platform: str,
        app_version: str | None,
    ) -> None:
        now = datetime.now(timezone.utc)
        existing = self.session.exec(
            select(DeviceToken).where(DeviceToken.token == token)
        ).first()
        if existing is not None:
            existing.user_id = user_id
            existing.platform = platform
            existing.app_version = app_version
            existing.last_seen_at = now
            existing.revoked_at = None
            self.session.add(existing)
        else:
            self.session.add(
                DeviceToken(
                    user_id=user_id,
                    token=token,
                    platform=platform,
                    app_version=app_version,
                    created_at=now,
                    last_seen_at=now,
                )
            )
        self.session.commit()

    def revoke(self, *, user_id: UUID, token: str) -> None:
        existing = self.session.exec(
            select(DeviceToken).where(
                DeviceToken.token == token, DeviceToken.user_id == user_id
            )
        ).first()
        if existing is None:
            return
        existing.revoked_at = datetime.now(timezone.utc)
        self.session.add(existing)
        self.session.commit()

    def list_active_for_user(self, user_id: UUID) -> list[DeviceTokenRecord]:
        rows = self.session.exec(
            select(DeviceToken).where(
                DeviceToken.user_id == user_id, DeviceToken.revoked_at.is_(None)
            )
        ).all()
        return [
            DeviceTokenRecord(
                user_id=r.user_id,
                token=r.token,
                platform=r.platform,
                app_version=r.app_version,
                last_seen_at=r.last_seen_at,
                revoked_at=r.revoked_at,
            )
            for r in rows
        ]
