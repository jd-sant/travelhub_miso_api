import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session


@pytest.fixture(scope="session", autouse=True)
def search_test_environment():
    patch = pytest.MonkeyPatch()
    patch.setenv("DATABASE_URL", "sqlite://")
    patch.setenv("ENV", "test")
    patch.setenv("APP_ENV", "test")
    patch.setenv("REDIS_CACHE_ENABLED", "false")  # disabled by default; test_cache.py uses fakeredis
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
def fake_redis():
    """In-memory Redis using fakeredis. No server required."""
    import fakeredis
    return fakeredis.FakeRedis(decode_responses=True)


@pytest.fixture
def cache(fake_redis):
    from adapters.cache.redis_cache import RedisCache
    from core.config import settings
    return RedisCache(client=fake_redis, ttl=settings.redis_cache_ttl_seconds)


@pytest.fixture
def search_repository(db_session):
    from adapters.repositories import SQLModelSearchRepository

    return SQLModelSearchRepository(db_session)


@pytest.fixture
def search_repository_with_cache(db_session, cache):
    from adapters.repositories import SQLModelSearchRepository

    return SQLModelSearchRepository(db_session, cache)


@pytest.fixture
def search_use_case(search_repository):
    from domain.use_cases import SearchPropertiesUseCase

    return SearchPropertiesUseCase(search_repository)


@pytest.fixture
def search_use_case_factory():
    """
    Returns a callable for performance tests.
    Each invocation opens and closes its own Session to avoid leaks in concurrent runs.
    """
    from db.session import engine
    from adapters.repositories import SQLModelSearchRepository
    from domain.use_cases import SearchPropertiesUseCase
    from sqlmodel import Session

    def _factory():
        def run_search(payload):
            with Session(engine) as session:
                repo = SQLModelSearchRepository(session)
                use_case = SearchPropertiesUseCase(repo)
                return use_case.execute(payload)

        return run_search

    return _factory
