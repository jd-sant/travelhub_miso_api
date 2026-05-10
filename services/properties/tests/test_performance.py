"""Performance tests for property detail endpoint"""
import time

import pytest
from fastapi.testclient import TestClient

from db.seed import RENAISSANCE_ESTATE_ID, DEMO_HOTEL_A_OWNER_ID


@pytest.mark.performance
def test_detail_p95_bajo_500ms(client: TestClient):
    """CA-PERF-1: P95 latency for property detail endpoint must be under 500ms"""
    ITERATIONS = 50
    latencies = []

    for _ in range(ITERATIONS):
        start = time.perf_counter()
        response = client.get(f"/api/v1/properties/{RENAISSANCE_ESTATE_ID}")
        elapsed_ms = (time.perf_counter() - start) * 1000
        assert response.status_code == 200
        latencies.append(elapsed_ms)

    latencies.sort()
    p50 = latencies[int(ITERATIONS * 0.50) - 1]
    p95 = latencies[int(ITERATIONS * 0.95) - 1]
    p99 = latencies[int(ITERATIONS * 0.99) - 1]

    print(f"\n[PERF] Property detail latency over {ITERATIONS} requests:")
    print(f"  P50 = {p50:.2f} ms")
    print(f"  P95 = {p95:.2f} ms")
    print(f"  P99 = {p99:.2f} ms")
    print(f"  Min = {min(latencies):.2f} ms")
    print(f"  Max = {max(latencies):.2f} ms")

    assert p95 < 500, f"P95 latency {p95:.2f}ms exceeds 500ms threshold"


@pytest.mark.performance
def test_seasonal_pricing_signature_p95_under_300ms(client: TestClient):
    """
    HU CA: P95 latency for seasonal pricing signature generation/verification
    must be under 300ms (goal: <300ms extremo a extremo).
    """
    admin_bearer = f"Bearer {DEMO_HOTEL_A_OWNER_ID}"
    payload = {
        "season_start": "2026-06-01",
        "season_end": "2026-08-31",
        "price_per_night": 150.0,
        "currency": "COP",
        "tax_rate": 0.19,
        "cleaning_fee": 50.0,
    }
    
    ITERATIONS = 30
    write_latencies = []
    read_latencies = []
    
    # Create initial pricing
    create_response = client.post(
        f"/api/v1/properties/{RENAISSANCE_ESTATE_ID}/seasonal-pricing",
        json=payload,
        headers={"Authorization": admin_bearer},
    )
    assert create_response.status_code == 201
    pricing_id = create_response.json()["id"]
    
    # Measure write (create/update) latency with signature generation
    for i in range(ITERATIONS):
        payload_variant = {
            **payload,
            "price_per_night": 150.0 + i,  # Vary to avoid exact caching
        }
        start = time.perf_counter()
        response = client.post(
            f"/api/v1/properties/{RENAISSANCE_ESTATE_ID}/seasonal-pricing",
            json=payload_variant,
            headers={"Authorization": admin_bearer},
        )
        elapsed_ms = (time.perf_counter() - start) * 1000
        assert response.status_code == 201
        write_latencies.append(elapsed_ms)
    
    # Measure read (list/get) latency with signature verification
    for _ in range(ITERATIONS):
        start = time.perf_counter()
        response = client.get(
            f"/api/v1/properties/{RENAISSANCE_ESTATE_ID}/seasonal-pricing/{pricing_id}"
        )
        elapsed_ms = (time.perf_counter() - start) * 1000
        assert response.status_code == 200
        read_latencies.append(elapsed_ms)
    
    # Analyze percentiles
    write_latencies.sort()
    read_latencies.sort()
    
    write_p95 = write_latencies[int(ITERATIONS * 0.95) - 1]
    read_p95 = read_latencies[int(ITERATIONS * 0.95) - 1]
    combined_p95 = max(write_p95, read_p95)
    
    print(f"\n[PERF] Seasonal pricing signature flow over {ITERATIONS} iterations:")
    print(f"  Write (create) P95 = {write_p95:.2f} ms (min={min(write_latencies):.2f}, max={max(write_latencies):.2f})")
    print(f"  Read (get) P95    = {read_p95:.2f} ms (min={min(read_latencies):.2f}, max={max(read_latencies):.2f})")
    print(f"  Combined P95      = {combined_p95:.2f} ms")
    
    # Assertion: both write and read must be under 300ms p95
    assert write_p95 < 300, f"Write P95 latency {write_p95:.2f}ms exceeds 300ms threshold"
    assert read_p95 < 300, f"Read P95 latency {read_p95:.2f}ms exceeds 300ms threshold"
