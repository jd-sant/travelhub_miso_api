from abc import ABC, abstractmethod
from datetime import datetime


class ReservationScheduler(ABC):
    @abstractmethod
    def schedule_reservation_expiration(self, reservation_id: str) -> str:
        """Schedule expiration check for a reservation and return schedule name."""

    @abstractmethod
    def cancel_reservation_expiration(self, reservation_id: str) -> None:
        """Cancel expiration schedule for a reservation if it exists."""

    @abstractmethod
    def schedule_arrival_reminder(
        self, reservation_id: str, fire_at: datetime
    ) -> str:
        """Schedule one-shot arrival reminder for a reservation."""

    @abstractmethod
    def cancel_arrival_reminder(self, reservation_id: str) -> None:
        """Cancel arrival reminder schedule if it exists."""
