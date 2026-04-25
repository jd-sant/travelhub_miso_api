"""Performance tests for reservations listing endpoint (HU Mis Reservas)"""
import time
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from domain.schemas.property_service import PropertyDetailResponse, PropertyCancellationPolicyResponse
from domain.schemas.reservation import CancellationPolicyType
from entrypoints.api.main import app
from entrypoints.api.routers.reservations import get_property_service_client


class _FastFakePropertyClient:
    def get_property(self, property_id):
        return PropertyDetailResponse(
            id=property_id,
            max_guests=10,
            name="Propiedad Performance",
            cover_image_url="https://example.com/img.jpg",
        )

    def get_cancellation_policy(self, property_id):
        now = datetime.now(UTC)
        return PropertyCancellationPolicyResponse(
            property_id=property_id,
            policy_type=CancellationPolicyType.full_refund,
            minimum_notice_hours=24,
            penalty_percentage=Decimal("0.00"),
            timezone="UTC",
            is_active=True,
            created_at=now,
            updated_at=now,
        )


@pytest.fixture
def perf_client(session):
    from db.session import get_session
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_property_service_client] = lambda: _FastFakePropertyClient()
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


@pytest.fixture
def traveler_with_reservations(perf_client):
    """Create a traveler with 10 reservations for perf testing."""
    traveler_id = str(uuid4())
    now = datetime.now(UTC)
    for i in range(10):
        payload = {
            "id_traveler": traveler_id,
            "id_property": str(uuid4()),
            "id_room": str(uuid4()),
            "check_in_date": (now + timedelta(days=10 + i)).isoformat(),
            "check_out_date": (now + timedelta(days=12 + i)).isoformat(),
            "number_of_guests": 2,
            "currency": "USD",
        }
        perf_client.post("/api/v1/reservations", json=payload)
    return traveler_id


@pytest.mark.performance
def test_list_reservations_p95_bajo_1s(perf_client, traveler_with_reservations):
    """CA-PERF: P95 de GET /reservations/users/{id} debe ser < 1000ms."""
    ITERATIONS = 50
    latencies = []
    url = f"/api/v1/reservations/users/{traveler_with_reservations}"

    for _ in range(ITERATIONS):
        start = time.perf_counter()
        response = perf_client.get(url)
        elapsed_ms = (time.perf_counter() - start) * 1000
        assert response.status_code == 200
        latencies.append(elapsed_ms)

    latencies.sort()
    p50 = latencies[int(ITERATIONS * 0.50) - 1]
    p95 = latencies[int(ITERATIONS * 0.95) - 1]
    p99 = latencies[int(ITERATIONS * 0.99) - 1]

    print(f"\n[PERF] Listado reservas por viajero (10 reservas, {ITERATIONS} peticiones):")
    print(f"  P50 = {p50:.2f} ms")
    print(f"  P95 = {p95:.2f} ms")
    print(f"  P99 = {p99:.2f} ms")
    print(f"  Min = {min(latencies):.2f} ms")
    print(f"  Max = {max(latencies):.2f} ms")

    assert p95 < 1000, f"P95 latency {p95:.2f}ms exceeds 1000ms threshold"
