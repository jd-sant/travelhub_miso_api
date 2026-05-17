from abc import ABC, abstractmethod
from typing import Optional
from uuid import UUID

from domain.schemas.reservation import ReservationCommandType


class ReservationCommandLogRepository(ABC):
    @abstractmethod
    def get_by_idempotency(
        self,
        reservation_id: UUID,
        command_type: ReservationCommandType,
        idempotency_key: str,
    ) -> Optional[dict]:
        pass

    @abstractmethod
    def add(
        self,
        reservation_id: UUID,
        command_type: ReservationCommandType,
        idempotency_key: str,
        response_payload: dict,
    ) -> None:
        pass
