import os
import sys
from pathlib import Path

import pytest
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

# Forzar SQLite en pruebas antes de importar el módulo de la app.
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["NOTIFICATIONS_SERVICE_URL"] = ""
os.environ["PAYMENTS_SERVICE_URL"] = ""
os.environ["JWT_SECRET_KEY"] = "test-secret-key"

SRC_PATH = Path(__file__).resolve().parents[1] / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from adapters.models.reservation import Reservation
from adapters.models.reservation_command_log import ReservationCommandLog
from adapters.models.reservation_event import ReservationEvent
from adapters.models.reservation_internal_note import ReservationInternalNote
from adapters.repositories.reservation_command_log_repository import (
    SQLModelReservationCommandLogRepository,
)
from adapters.repositories.reservation_event_repository import (
    SQLModelReservationEventRepository,
)
from adapters.repositories.reservation_repository import SQLModelReservationRepository
from db.session import get_session
from domain.schemas.reservation import ReservationCreateRequest, ReservationResponse
from domain.use_cases.create_reservation import CreateReservationUseCase
from entrypoints.api.main import app


@pytest.fixture
def session():
    """Create an in-memory SQLite database for testing."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    _ = (Reservation, ReservationEvent, ReservationCommandLog, ReservationInternalNote)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture
def client(session):
    """Create a test client with test database dependency."""

    def get_session_override():
        return session

    app.dependency_overrides[get_session] = get_session_override
    test_client = TestClient(app)
    yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def reservation_repository(session: Session):
    """Create a repository instance with test session."""
    return SQLModelReservationRepository(session)


@pytest.fixture
def reservation_event_repository(session: Session):
    """Create event repository instance with test session."""
    return SQLModelReservationEventRepository(session)


@pytest.fixture
def reservation_command_log_repository(session: Session):
    """Create command-log repository instance with test session."""
    return SQLModelReservationCommandLogRepository(session)


@pytest.fixture
def create_reservation_use_case(reservation_repository):
    """Create use case instance with test repository."""
    return CreateReservationUseCase(reservation_repository)


@pytest.fixture
def traveler_id():
    return uuid4()


@pytest.fixture
def property_id():
    return uuid4()


@pytest.fixture
def room_id():
    return uuid4()


@pytest.fixture
def valid_create_request(traveler_id, property_id, room_id):
    """Create a valid reservation request."""
    check_in = datetime.now(UTC) + timedelta(days=5)
    check_out = check_in + timedelta(days=3)

    return ReservationCreateRequest(
        id_traveler=traveler_id,
        id_property=property_id,
        id_room=room_id,
        check_in_date=check_in,
        check_out_date=check_out,
        number_of_guests=2,
        currency="COP",
    )
