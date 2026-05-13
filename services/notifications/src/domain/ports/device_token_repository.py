from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class DeviceTokenRecord:
    user_id: UUID
    token: str
    platform: str
    app_version: str | None
    last_seen_at: datetime
    revoked_at: datetime | None


class DeviceTokenRepository(ABC):
    @abstractmethod
    def upsert(
        self,
        *,
        user_id: UUID,
        token: str,
        platform: str,
        app_version: str | None,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    def revoke(self, *, user_id: UUID, token: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def list_active_for_user(self, user_id: UUID) -> list[DeviceTokenRecord]:
        raise NotImplementedError
