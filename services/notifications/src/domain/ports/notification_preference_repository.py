from abc import ABC, abstractmethod
from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class NotificationPreferenceRecord:
    user_id: UUID
    status_changes_enabled: bool = True
    arrival_reminders_enabled: bool = True


class NotificationPreferenceRepository(ABC):
    @abstractmethod
    def get(self, user_id: UUID) -> NotificationPreferenceRecord:
        """Devuelve la preferencia o defaults (todo activo) si no existe."""
        raise NotImplementedError

    @abstractmethod
    def upsert(
        self,
        *,
        user_id: UUID,
        status_changes_enabled: bool | None = None,
        arrival_reminders_enabled: bool | None = None,
    ) -> NotificationPreferenceRecord:
        raise NotImplementedError
