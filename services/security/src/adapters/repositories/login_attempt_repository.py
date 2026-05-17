from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlmodel import Session, func, select

from adapters.models.login_attempt import LoginAttempt
from domain.ports.login_attempt_repository import (
    LoginAttemptRepository as LoginAttemptRepositoryPort,
)


class SQLModelLoginAttemptRepository(LoginAttemptRepositoryPort):
    def __init__(self, session: Session):
        self.session = session

    def record(
        self,
        ip_address: str,
        success: bool,
        user_id: Optional[UUID] = None,
        failure_reason: Optional[str] = None,
    ) -> None:
        attempt = LoginAttempt(
            user_id=user_id,
            ip_address=ip_address,
            success=success,
            failure_reason=failure_reason,
        )
        self.session.add(attempt)
        self.session.commit()

    def count_failed_by_ip(self, ip: str, since: datetime) -> int:
        result = self.session.exec(
            select(func.count())
            .select_from(LoginAttempt)
            .where(LoginAttempt.ip_address == ip)
            .where(LoginAttempt.success == False)  # noqa: E712
            .where(LoginAttempt.created_at >= since)
        ).one()
        return result
