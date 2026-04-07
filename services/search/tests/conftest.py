import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["ENV"] = "test"
os.environ["APP_ENV"] = "test"

SRC_PATH = Path(__file__).resolve().parents[1] / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from entrypoints.api.main import app
from adapters.repositories import SQLModelSearchRepository
from domain.use_cases import SearchPropertiesUseCase
from db.seed import seed_dummy_data_if_needed
from db.session import create_db_and_tables, engine


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="session", autouse=True)
def seed_dummy_data_for_local_db():
    create_db_and_tables()
    seed_dummy_data_if_needed()


@pytest.fixture
def db_session():
    with Session(engine) as session:
        yield session


@pytest.fixture
def search_repository(db_session):
    return SQLModelSearchRepository(db_session)


@pytest.fixture
def search_use_case(search_repository):
    return SearchPropertiesUseCase(search_repository)
