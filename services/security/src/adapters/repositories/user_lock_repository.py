from datetime import datetime
from typing import Optional

from sqlalchemy import delete as sa_delete
from sqlmodel import Session, select

from adapters.models.user_lock import UserLock
from domain.ports.user_lock_repository import (
    UserLockRepository as UserLockRepositoryPort,
)
from domain.schemas.auth import UserLockRecord


class SQLModelUserLockRepository(UserLockRepositoryPort):
    def __init__(self, session: Session):
        self.session = session

    def get_lock(self, email: str) -> Optional[UserLockRecord]:
        model = self.session.exec(
            select(UserLock).where(UserLock.email == email)
        ).first()
        return UserLockRecord.model_validate(model) if model else None

    def create_lock(self, email: str, locked_until: datetime) -> None:
        existing = self.session.exec(
            select(UserLock).where(UserLock.email == email)
        ).first()
        if existing:
            existing.locked_until = locked_until
            self.session.add(existing)
        else:
            lock = UserLock(email=email, locked_until=locked_until)
            self.session.add(lock)
        self.session.commit()

    def delete_lock(self, email: str) -> None:
        self.session.execute(
            sa_delete(UserLock).where(UserLock.email == email)
        )
        self.session.commit()
