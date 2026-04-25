"""Performance tests for property detail endpoint"""
import time

import pytest
from fastapi.testclient import TestClient

from db.seed import RENAISSANCE_ESTATE_ID


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
