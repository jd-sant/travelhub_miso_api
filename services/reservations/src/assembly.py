from collections.abc import Generator
from contextlib import contextmanager

from sqlmodel import Session

from adapters.repositories.reservation_repository import SQLModelReservationRepository
from db.session import get_session
from domain.use_cases.check_reservation_status import CheckReservationStatusUseCase
from domain.use_cases.create_reservation import CreateReservationUseCase
from domain.use_cases.update_reservation import UpdateReservationStatusUseCase


class ReservationAssembly:
    """Dependency injection container for Reservations service."""

    @staticmethod
    @contextmanager
    def repository_scope() -> Generator[SQLModelReservationRepository, None, None]:
        """Create and close a repository/session for non-FastAPI callers."""
        session_generator = get_session()
        session = next(session_generator)
        try:
            yield SQLModelReservationRepository(session)
        finally:
            session.close()
            session_generator.close()

    @staticmethod
    def get_reservation_repository(session: Session) -> SQLModelReservationRepository:
        return SQLModelReservationRepository(session)

    @staticmethod
    def get_create_reservation_use_case(
        repository: SQLModelReservationRepository,
    ) -> CreateReservationUseCase:
        return CreateReservationUseCase(repository)

    @staticmethod
    def get_update_reservation_status_use_case(
        repository: SQLModelReservationRepository,
    ) -> UpdateReservationStatusUseCase:
        return UpdateReservationStatusUseCase(repository)

    @staticmethod
    def get_check_reservation_status_use_case(
        updater: UpdateReservationStatusUseCase,
    ) -> CheckReservationStatusUseCase:
        return CheckReservationStatusUseCase(updater)
