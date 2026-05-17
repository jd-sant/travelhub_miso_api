from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

from domain.schemas.auth import UserLockRecord


class UserLockRepository(ABC):
    @abstractmethod
    def get_lock(self, email: str) -> Optional[UserLockRecord]:
        pass

    @abstractmethod
    def create_lock(self, email: str, locked_until: datetime) -> None:
        pass

    @abstractmethod
    def delete_lock(self, email: str) -> None:
        pass
