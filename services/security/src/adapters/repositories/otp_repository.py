from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import update
from sqlmodel import Session, select

from adapters.models.otp_code import OtpCode
from domain.ports.otp_repository import OtpRepository as OtpRepositoryPort
from domain.schemas.auth import OtpRecord


class SQLModelOtpRepository(OtpRepositoryPort):
    def __init__(self, session: Session):
        self.session = session

    def create(
        self,
        user_id: UUID,
        email: str,
        code: str,
        expires_at: datetime,
        roles: list[str],
    ) -> None:
        otp = OtpCode(
            user_id=user_id,
            email=email,
            code=code,
            expires_at=expires_at,
            roles=",".join(roles),
        )
        self.session.add(otp)
        self.session.commit()

    def get_active(self, email: str) -> Optional[OtpRecord]:
        now = datetime.now(timezone.utc)
        model = self.session.exec(
            select(OtpCode)
            .where(OtpCode.email == email)
            .where(OtpCode.is_used == False)  # noqa: E712
            .where(OtpCode.expires_at > now)
            .order_by(OtpCode.created_at.desc())
        ).first()
        return OtpRecord.model_validate(model) if model else None

    def increment_attempts(self, otp_id: UUID) -> int:
        otp = self.session.get(OtpCode, otp_id)
        if otp:
            otp.attempts += 1
            self.session.add(otp)
            self.session.commit()
            self.session.refresh(otp)
            return otp.attempts
        return 0

    def mark_used(self, otp_id: UUID) -> None:
        otp = self.session.get(OtpCode, otp_id)
        if otp:
            otp.is_used = True
            self.session.add(otp)
            self.session.commit()

    def invalidate_all(self, email: str) -> None:
        self.session.execute(
            update(OtpCode)
            .where(OtpCode.email == email)
            .where(OtpCode.is_used == False)  # noqa: E712
            .values(is_used=True)
        )
        self.session.commit()
