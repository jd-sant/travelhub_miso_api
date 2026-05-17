from abc import ABC, abstractmethod
from uuid import UUID

from domain.schemas.notification import TravelerProfileRecord


class TravelerProfileSource(ABC):
    @abstractmethod
    def get_traveler(self, traveler_id: UUID) -> TravelerProfileRecord:
        raise NotImplementedError
