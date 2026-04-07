import statistics
import time

import httpx

BASE_URL = "http://localhost:8003"
PATH = "/api/v1/search"
TOTAL_REQUESTS = 120
WARMUP_REQUESTS = 10
TIMEOUT_SECONDS = 10

PARAMS = {
    "ciudad": "Bogota",
    "check_in": "2026-04-10",
    "check_out": "2026-04-12",
    "huespedes": 2,
    "page": 1,
    "page_size": 10,
}


def percentile(values: list[float], p: int) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    k = max(0, min(len(ordered) - 1, int((p / 100) * (len(ordered) - 1))))
    return ordered[k]


def run() -> int:
    latencies_ms: list[float] = []

    with httpx.Client(base_url=BASE_URL, timeout=TIMEOUT_SECONDS) as client:
        health = client.get("/health")
        if health.status_code != 200:
            print(f"health check failed: {health.status_code}")
            return 1

        for _ in range(WARMUP_REQUESTS):
            response = client.get(PATH, params=PARAMS)
            if response.status_code != 200:
                print(f"warmup failed: {response.status_code} {response.text}")
                return 1

        for _ in range(TOTAL_REQUESTS):
            started = time.perf_counter()
            response = client.get(PATH, params=PARAMS)
            elapsed_ms = (time.perf_counter() - started) * 1000
            if response.status_code != 200:
                print(f"request failed: {response.status_code} {response.text}")
                return 1
            latencies_ms.append(elapsed_ms)

    p50 = percentile(latencies_ms, 50)
    p95 = percentile(latencies_ms, 95)
    p99 = percentile(latencies_ms, 99)
    avg = statistics.mean(latencies_ms)

    print(f"requests={TOTAL_REQUESTS}")
    print(f"avg_ms={avg:.2f}")
    print(f"p50_ms={p50:.2f}")
    print(f"p95_ms={p95:.2f}")
    print(f"p99_ms={p99:.2f}")

    if p95 < 800:
        print("result=PASS (p95 < 800ms)")
        return 0

    print("result=FAIL (p95 >= 800ms)")
    return 2


if __name__ == "__main__":
    raise SystemExit(run())
