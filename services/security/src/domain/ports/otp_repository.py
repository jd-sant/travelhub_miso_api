from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional
from uuid import UUID

from domain.schemas.auth import OtpRecord


class OtpRepository(ABC):
    @abstractmethod
    def create(
        self,
        user_id: UUID,
        email: str,
        code: str,
        expires_at: datetime,
        roles: list[str],
    ) -> None:
        pass

    @abstractmethod
    def get_active(self, email: str) -> Optional[OtpRecord]:
        pass

    @abstractmethod
    def increment_attempts(self, otp_id: UUID) -> int:
        pass

    @abstractmethod
    def mark_used(self, otp_id: UUID) -> None:
        pass

    @abstractmethod
    def invalidate_all(self, email: str) -> None:
        pass
