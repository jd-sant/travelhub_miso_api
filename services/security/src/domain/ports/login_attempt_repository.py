from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional
from uuid import UUID


class LoginAttemptRepository(ABC):
    @abstractmethod
    def record(
        self,
        ip_address: str,
        success: bool,
        user_id: Optional[UUID] = None,
        failure_reason: Optional[str] = None,
    ) -> None:
        pass

    @abstractmethod
    def count_failed_by_ip(self, ip: str, since: datetime) -> int:
        pass
