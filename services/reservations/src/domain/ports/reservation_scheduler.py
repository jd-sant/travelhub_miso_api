from abc import ABC, abstractmethod


class ReservationScheduler(ABC):
    @abstractmethod
    def schedule_reservation_expiration(self, reservation_id: str) -> str:
        """Schedule expiration check for a reservation and return schedule name."""

    @abstractmethod
    def cancel_reservation_expiration(self, reservation_id: str) -> None:
        """Cancel expiration schedule for a reservation if it exists."""
