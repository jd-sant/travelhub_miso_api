import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session


@pytest.fixture(scope="session", autouse=True)
def search_test_environment():
    patch = pytest.MonkeyPatch()
    patch.setenv("DATABASE_URL", "sqlite://")
    patch.setenv("ENV", "test")
    patch.setenv("APP_ENV", "test")
    yield
    patch.undo()


@pytest.fixture(scope="session")
def client():
    from entrypoints.api.main import app

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="session", autouse=True)
def seed_dummy_data_for_local_db():
    from db.seed import seed_dummy_data_if_needed
    from db.session import create_db_and_tables

    create_db_and_tables()
    seed_dummy_data_if_needed()


@pytest.fixture
def db_session():
    from db.session import engine

    with Session(engine) as session:
        yield session


@pytest.fixture
def search_repository(db_session):
    from adapters.repositories import SQLModelSearchRepository

    return SQLModelSearchRepository(db_session)


@pytest.fixture
def search_use_case(search_repository):
    from domain.use_cases import SearchPropertiesUseCase

    return SearchPropertiesUseCase(search_repository)
