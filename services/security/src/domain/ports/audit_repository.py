from abc import ABC, abstractmethod
from typing import Optional
from uuid import UUID


class AuditRepository(ABC):
    @abstractmethod
    def record(
        self,
        entity_type: str,
        action: str,
        ip_address: str,
        user_id: Optional[UUID] = None,
        entity_id: Optional[UUID] = None,
    ) -> None:
        pass
