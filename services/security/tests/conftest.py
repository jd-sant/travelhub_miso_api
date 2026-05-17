import os
from typing import Optional
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import delete as sa_delete
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-jwt")
os.environ.setdefault("INTERNAL_API_KEY", "test-internal-key")

from adapters.models.audit_log import AuditLog
from adapters.models.login_attempt import LoginAttempt
from adapters.models.otp_code import OtpCode
from adapters.models.sensitive_data_audit_log import SensitiveDataAuditLog
from adapters.models.user_lock import UserLock
from db.session import get_session
from domain.ports.auth_repository import AuthRepository
from domain.schemas.auth import UserCredentials
from entrypoints.api.routers.auth import router as auth_router


class FakeAuthRepository(AuthRepository):
    def __init__(self):
        self.users: dict[str, UserCredentials] = {}

    def add_user(self, email: str, user_id, status: int, roles: list[str]):
        self.users[email] = UserCredentials(
            id=user_id, email=email, status=status, roles=roles
        )

    def verify_credentials(
        self, email: str, password: str
    ) -> Optional[UserCredentials]:
        if email in self.users and password == "correctPassword":
            return self.users[email]
        return None


class FakeOtpSender:
    def __init__(self):
        self.sent: list[tuple[str, str]] = []

    def send(self, email: str, code: str) -> None:
        self.sent.append((email, code))


@pytest.fixture(scope="session")
def test_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture(autouse=True)
def _clean_tables(test_engine):
    with Session(test_engine) as session:
        session.execute(sa_delete(OtpCode))
        session.execute(sa_delete(LoginAttempt))
        session.execute(sa_delete(AuditLog))
        session.execute(sa_delete(SensitiveDataAuditLog))
        session.execute(sa_delete(UserLock))
        session.commit()


@pytest.fixture
def fake_auth_repo():
    repo = FakeAuthRepository()
    repo.add_user(
        email="ana@example.com",
        user_id=uuid4(),
        status=1,
        roles=["traveler"],
    )
    return repo


@pytest.fixture
def fake_otp_sender():
    return FakeOtpSender()


@pytest.fixture
def client(test_engine, fake_auth_repo, fake_otp_sender):
    from assembly import get_auth_repository, get_otp_sender

    app = FastAPI()
    app.include_router(auth_router, prefix="/api/v1")

    def override_get_session():
        with Session(test_engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_auth_repository] = lambda: fake_auth_repo
    app.dependency_overrides[get_otp_sender] = lambda: fake_otp_sender

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
