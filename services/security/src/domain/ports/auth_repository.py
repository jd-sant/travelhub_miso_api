from abc import ABC, abstractmethod
from typing import Optional

from domain.schemas.auth import UserCredentials


class AuthRepository(ABC):
    @abstractmethod
    def verify_credentials(
        self, email: str, password: str
    ) -> Optional[UserCredentials]:
        pass
