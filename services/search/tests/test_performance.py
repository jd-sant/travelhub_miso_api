"""
Tests de rendimiento que validan los Criterios de Aceptación de la historia MPF-71.

CA1: Bajo carga normal (≤150 TPM), P95 del endpoint /api/v1/search ≤ 800ms.
CA2: 100 búsquedas concurrentes → P95 ≤ 800ms, P99 ≤ 1200ms.
CA3: Cache hit ≤ 200ms (P95 de 20 llamadas tras warmup).

Ejecutar:
    pytest tests/test_performance.py -m performance -v

Notas de backend:
- CA1 y CA3 usan SQLite en memoria (disponibles en local y CI).
- CA2 requiere PostgreSQL para correcta concurrencia. En SQLite StaticPool
  todas las conexiones comparten el mismo hilo subyacente, por lo que los
  tests de concurrencia se omiten automáticamente al detectar SQLite.
  En CI, el job performance-gate levanta postgres + redis y los ejecuta.

Seeded dates en SQLite: 2026-04-10 y 2026-04-11
"""
import statistics
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date

import pytest

from domain.schemas.search import SearchQuery
from core.config import settings

# Skip concurrent tests when using SQLite: StaticPool shares one connection,
# making multi-threaded SQLAlchemy sessions unsafe. These run in CI against PostgreSQL.
_is_sqlite = settings.database_url.startswith("sqlite")
requires_postgres = pytest.mark.skipif(
    _is_sqlite,
    reason="CA2 concurrency tests require PostgreSQL; SQLite StaticPool is single-threaded.",
)

# ---------------------------------------------------------------------------
# Queries de referencia — usan las fechas de seed (SEED_DATES en db/seed.py)
# ---------------------------------------------------------------------------
SEARCH_QUERIES = [
    SearchQuery(city="Bogota",       check_in=date(2026, 4, 10), check_out=date(2026, 4, 11), guests=2),
    SearchQuery(city="Cartagena",    check_in=date(2026, 4, 10), check_out=date(2026, 4, 11), guests=4),
    SearchQuery(city="Cali",         check_in=date(2026, 4, 10), check_out=date(2026, 4, 11), guests=3),
    SearchQuery(city="Barranquilla", check_in=date(2026, 4, 10), check_out=date(2026, 4, 11), guests=2),
    SearchQuery(city="Santa Marta",  check_in=date(2026, 4, 10), check_out=date(2026, 4, 11), guests=2),
    SearchQuery(city="Bucaramanga",  check_in=date(2026, 4, 10), check_out=date(2026, 4, 11), guests=2),
    SearchQuery(city="Bogota",       check_in=date(2026, 4, 10), check_out=date(2026, 4, 11), guests=2,
                amenities=["wifi"]),
    SearchQuery(city="Bogota",       check_in=date(2026, 4, 10), check_out=date(2026, 4, 11), guests=2,
                order_by="rating", order_dir="desc"),
]


def _p(latencies: list[float], percentile: int) -> float:
    """Calcula el percentil usando statistics.quantiles (n=100)."""
    if len(latencies) < percentile:
        # Si hay menos muestras que el percentil requerido, usa el máximo
        return max(latencies)
    qs = statistics.quantiles(latencies, n=100)
    return qs[percentile - 1]  # índice 0-based: percentile 95 → índice 94


# ---------------------------------------------------------------------------
# Criterios de Aceptación
# ---------------------------------------------------------------------------

@pytest.mark.performance
class TestCriteriosDeAceptacion:

    def test_ca3_cache_hit_bajo_200ms(self, search_repository_with_cache):
        """
        CA3: Cuando la caché contiene el resultado, el tiempo de respuesta P95 ≤ 200ms.
        Método: warmup de la primera llamada (miss), luego 20 llamadas consecutivas (hits).
        """
        query = SEARCH_QUERIES[0]

        # Warmup: puebla el caché
        search_repository_with_cache.search(query)

        latencies_ms = []
        for _ in range(20):
            start = time.perf_counter()
            search_repository_with_cache.search(query)
            latencies_ms.append((time.perf_counter() - start) * 1000)

        p95 = _p(latencies_ms, 95)
        assert p95 <= 200, (
            f"CA3 FALLO: Cache hit P95={p95:.1f}ms supera 200ms. "
            f"Max={max(latencies_ms):.1f}ms, Min={min(latencies_ms):.1f}ms"
        )

    def test_ca1_p95_bajo_800ms_carga_normal(self, search_use_case):
        """
        CA1: Bajo carga normal (≤150 TPM), el endpoint retorna resultados con P95 ≤ 800ms.
        Método: 150 llamadas secuenciales con queries variadas (todas las ciudades seeded).
        """
        latencies_ms = []
        for i in range(150):
            query = SEARCH_QUERIES[i % len(SEARCH_QUERIES)]
            start = time.perf_counter()
            search_use_case.execute(query)
            latencies_ms.append((time.perf_counter() - start) * 1000)

        p95 = _p(latencies_ms, 95)
        assert p95 <= 800, (
            f"CA1 FALLO: P95={p95:.1f}ms supera 800ms bajo carga normal. "
            f"Max={max(latencies_ms):.1f}ms, Mediana={statistics.median(latencies_ms):.1f}ms"
        )

    @requires_postgres
    def test_ca2_100_concurrentes_p95_800ms_p99_1200ms(self, search_use_case_factory):
        """
        CA2: 100 búsquedas concurrentes → P95 ≤ 800ms y P99 ≤ 1200ms.
        Método: ThreadPoolExecutor con 100 workers como proxy de 100 usuarios concurrentes.
        Cada thread crea su propio use_case con sesión independiente (SQLite thread safety).
        """
        latencies_ms: list[float] = []
        errors: list[str] = []

        def run(idx: int) -> float:
            use_case = search_use_case_factory()
            query = SEARCH_QUERIES[idx % len(SEARCH_QUERIES)]
            start = time.perf_counter()
            use_case.execute(query)
            return (time.perf_counter() - start) * 1000

        with ThreadPoolExecutor(max_workers=100) as pool:
            futures = [pool.submit(run, i) for i in range(100)]
            for future in as_completed(futures):
                try:
                    latencies_ms.append(future.result())
                except Exception as exc:
                    errors.append(str(exc))

        assert not errors, f"CA2 FALLO: Errores durante carga concurrente: {errors}"

        p95 = _p(latencies_ms, 95)
        p99 = _p(latencies_ms, 99)

        assert p95 <= 800, (
            f"CA2 FALLO: P95={p95:.1f}ms supera 800ms bajo 100 concurrentes. "
            f"p99={p99:.1f}ms, Max={max(latencies_ms):.1f}ms"
        )
        assert p99 <= 1200, (
            f"CA2 FALLO: P99={p99:.1f}ms supera 1200ms bajo 100 concurrentes. "
            f"p95={p95:.1f}ms, Max={max(latencies_ms):.1f}ms"
        )

    @requires_postgres
    def test_ca2_tasa_de_error_menor_1_porciento(self, search_use_case_factory):
        """
        CA2 (complementario): Error rate < 1% bajo carga concurrente sostenida.
        Cada thread usa su propio use_case para evitar problemas de concurrencia en SQLite.
        """
        total = 100
        errors = 0

        def run_one(idx: int):
            return search_use_case_factory().execute(SEARCH_QUERIES[idx % len(SEARCH_QUERIES)])

        with ThreadPoolExecutor(max_workers=20) as pool:
            futures = [pool.submit(run_one, i) for i in range(total)]
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception:
                    errors += 1

        error_rate = errors / total * 100
        assert error_rate < 1, (
            f"CA2 FALLO: Error rate {error_rate:.1f}% supera el 1% permitido "
            f"({errors}/{total} errores)"
        )
