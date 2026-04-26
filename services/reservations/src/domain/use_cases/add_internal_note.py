from uuid import UUID

from domain.ports.reservation_repository import ReservationRepository
from domain.schemas.reservation import InternalNoteResponse
from errors import ReservationNotFoundError


class AddInternalNoteUseCase:
    def __init__(self, repository: ReservationRepository):
        self.repository = repository

    def execute(
        self,
        reservation_id: UUID,
        content: str,
        author_user_id: UUID,
        author_name: str | None = None,
    ) -> InternalNoteResponse:
        reservation = self.repository.get_by_id(reservation_id)
        if reservation is None:
            raise ReservationNotFoundError("Reservation not found")

        return self.repository.add_note(
            reservation_id=reservation_id,
            content=content,
            author_user_id=author_user_id,
            author_name=author_name,
        )
