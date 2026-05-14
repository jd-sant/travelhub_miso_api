from datetime import date
from decimal import Decimal
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from domain.schemas.availability import PropertyAvailabilityQuery, PropertyAvailabilityResponse


@pytest.fixture(scope="session", autouse=True)
def inventory_test_environment():
    patch = pytest.MonkeyPatch()
    patch.setenv("ENV", "test")
    patch.setenv("APP_ENV", "test")
    patch.setenv("INTERNAL_API_KEY", "test-internal-key")
    patch.setenv("JWT_SECRET_KEY", "test-jwt-secret")
    yield
    patch.undo()


class FakeAvailabilityUseCase:
    def execute(self, query: PropertyAvailabilityQuery) -> PropertyAvailabilityResponse:
        available = query.check_in.isoformat() != "2026-04-12"
        return PropertyAvailabilityResponse(
            property_id=query.property_id,
            check_in=query.check_in,
            check_out=query.check_out,
            guests=query.guests,
            available=available,
            price_from=Decimal("180000.00") if available else None,
            currency="COP" if available else None,
        )


@pytest.fixture
def client():
    from entrypoints.api.main import app

    test_client = TestClient(app)
    yield test_client
    app.dependency_overrides.clear()
