import os
import sys
from pathlib import Path
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

# Forzar SQLite en pruebas antes de importar el módulo de la app.
os.environ["DATABASE_URL"] = "sqlite://"

SRC_PATH = Path(__file__).resolve().parents[1] / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from adapters.services.security_client import SecurityClient, TokenClaims  # noqa: E402
from assembly import get_security_client  # noqa: E402
from db.seed import sync_demo_properties_seed  # noqa: E402
from db.session import get_session  # noqa: E402
from entrypoints.api.main import app  # noqa: E402


def bearer_for_admin(admin_id: str | UUID) -> str:
    """Build the Authorization header value used by tests.

    The bearer payload is just the admin UUID; the FakeSecurityClient below
    interprets it as the user_id for token validation. This keeps the JWT
    secret out of properties entirely.
    """
    return f"Bearer {admin_id}"


class FakeSecurityClient(SecurityClient):
    """Test double that treats the bearer string as the admin UUID."""

    def __init__(self):  # type: ignore[no-untyped-def]
        pass

    def validate_token(self, token: str) -> TokenClaims | None:
        try:
            user_id = UUID(token.strip())
        except (ValueError, AttributeError):
            return None
        return TokenClaims(user_id=user_id, email="admin@test", role="admin")


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
    """Create a test client with the app and a fake security client wired in."""

    def get_session_override():
        return session

    def get_security_client_override():
        return FakeSecurityClient()

    app.dependency_overrides[get_session] = get_session_override
    app.dependency_overrides[get_security_client] = get_security_client_override

    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()
