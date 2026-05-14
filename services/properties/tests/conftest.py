import os
import sys
from uuid import UUID
from pathlib import Path

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

# Forzar SQLite en pruebas antes de importar el módulo de la app.
os.environ["DATABASE_URL"] = "sqlite://"

SRC_PATH = Path(__file__).resolve().parents[1] / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from core.config import settings
from db.session import get_session
from db.seed import sync_demo_properties_seed
from entrypoints.api.main import app


def jwt_for_admin(admin_id: str | UUID) -> str:
    """Generate a valid JWT for a given admin ID for testing."""
    return jwt.encode(
        {"sub": str(admin_id)},
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


@pytest.fixture(name="session")
def session_fixture():
    """Create an in-memory SQLite database for testing"""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    
    # Seed database with sample data
    with Session(engine) as session:
        sync_demo_properties_seed(session)
    
    with Session(engine) as session:
        yield session


@pytest.fixture(name="client")
def client_fixture(session: Session):
    """Create a test client with the app"""
    def get_session_override():
        return session

    from fastapi.testclient import TestClient
    from assembly import get_property_repository

    app.dependency_overrides[get_session] = get_session_override

    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()

