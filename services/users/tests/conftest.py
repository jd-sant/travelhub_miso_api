import os
import sys
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import delete as sa_delete
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine

from adapters.models.role import Role
from adapters.models.user import User
from adapters.models.user_role import UserRole
from core.auth_middleware import AuthMiddleware
from core.roles import UserRole as UserRoleEnum
from db.session import get_session
from entrypoints.api.routers.internal import router as internal_router
from entrypoints.api.routers.users import router as users_router

# Make tests/ importable so helpers.py can be used
sys.path.insert(0, os.path.dirname(__file__))

from helpers import INTERNAL_API_KEY 


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
        session.execute(sa_delete(UserRole))
        session.execute(sa_delete(Role))
        session.execute(sa_delete(User))
        session.commit()


@pytest.fixture
def session(test_engine):
    with Session(test_engine) as session:
        yield session


@pytest.fixture
def client(test_engine):
    os.environ["INTERNAL_API_KEY"] = INTERNAL_API_KEY
    os.environ["JWT_SECRET_KEY"] = "test-secret-key"
    os.environ["USERS_EMAIL_LOOKUP_HASH_SECRET"] = "test-users-email-lookup-hash-secret"
    os.environ["USERS_PII_ENCRYPTION_KEY"] = "test-users-pii-key"

    app = FastAPI()
    
    # Registra el middleware de autenticación
    app.add_middleware(AuthMiddleware)
    
    app.include_router(users_router, prefix="/api/v1")
    app.include_router(internal_router, prefix="/api/v1")

    def override_get_session():
        with Session(test_engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def _create_jwt_token(user_id: str, email: str, role: str) -> str:
    """Helper para crear JWT tokens de prueba"""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "email": email,
        "role": role,
        "iat": now,
        "exp": now + timedelta(minutes=30),
        "jti": str(uuid4()),
    }
    return jwt.encode(payload, "test-secret-key", algorithm="HS256")


@pytest.fixture
def admin_token():
    """Token JWT para usuario admin"""
    return _create_jwt_token(str(uuid4()), "admin@example.com", "admin")


@pytest.fixture
def traveler_token():
    """Token JWT para usuario viajero"""
    return _create_jwt_token(str(uuid4()), "traveler@example.com", "traveler")


@pytest.fixture
def hotel_token():
    """Token JWT para usuario hotel"""
    return _create_jwt_token(str(uuid4()), "hotel@example.com", "hotel")
