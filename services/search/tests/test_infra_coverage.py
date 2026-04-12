from __future__ import annotations

import importlib.util
from pathlib import Path
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest

from db import seed as seed_module
from db import session as session_module
from domain.schemas import SearchQuery
from entrypoints.api.routers import search as search_router
from errors import InvalidSearchRuleError


_PERF_MODULE_PATH = Path(__file__).with_name("test_performance.py")
_PERF_SPEC = importlib.util.spec_from_file_location("search_test_performance", _PERF_MODULE_PATH)
assert _PERF_SPEC is not None and _PERF_SPEC.loader is not None
perf_module = importlib.util.module_from_spec(_PERF_SPEC)
_PERF_SPEC.loader.exec_module(perf_module)


def test_search_router_rule_validations_and_pagination():
    with pytest.raises(InvalidSearchRuleError, match="check_out"):
        search_router._validate_search_rules(
            SearchQuery(
                city="Bogota",
                check_in=date(2026, 4, 12),
                check_out=date(2026, 4, 11),
                guests=2,
            )
        )

    with pytest.raises(InvalidSearchRuleError, match="min_price"):
        search_router._validate_search_rules(
            SearchQuery(
                city="Bogota",
                check_in=date(2026, 4, 10),
                check_out=date(2026, 4, 12),
                guests=2,
                min_price=Decimal("300"),
                max_price=Decimal("200"),
            )
        )

    with pytest.raises(InvalidSearchRuleError, match="order_by"):
        search_router._validate_search_rules(
            SearchQuery(
                city="Bogota",
                check_in=date(2026, 4, 10),
                check_out=date(2026, 4, 12),
                guests=2,
                order_by="distance",
            )
        )

    with pytest.raises(InvalidSearchRuleError, match="order_dir"):
        search_router._validate_search_rules(
            SearchQuery(
                city="Bogota",
                check_in=date(2026, 4, 10),
                check_out=date(2026, 4, 12),
                guests=2,
                order_dir="sideways",
            )
        )

    assert search_router._calculate_total_pages(total=0, page_size=10) == 0
    assert search_router._calculate_total_pages(total=23, page_size=10) == 3


def test_seed_helpers_and_metadata_drift_detection():
    days = seed_module._build_seed_dates()
    assert len(days) == 12 * 7
    assert days[0] == date(2026, 1, 10)
    assert days[-1] == date(2026, 12, 16)

    assert seed_module._build_local_seed_image_url(1).endswith("hotel-01.jpg")
    assert seed_module._build_local_seed_image_url(25).endswith("hotel-01.jpg")
    assert seed_module._build_seed_price(Decimal("99.99"), date(2026, 4, 10)) == Decimal("99.99")

    class _SessionMissing:
        def exec(self, *_args, **_kwargs):
            class _Q:
                @staticmethod
                def all():
                    return []

            return _Q()

    assert seed_module._has_seed_metadata_drift(_SessionMissing()) is True


def test_seed_enablement_matrix(monkeypatch):
    monkeypatch.setattr(seed_module, "engine", SimpleNamespace(url="sqlite:///tmp.db"))
    monkeypatch.setattr(seed_module, "settings", SimpleNamespace(is_local_dev=False))
    assert seed_module._is_seed_enabled() is True

    monkeypatch.setattr(seed_module, "engine", SimpleNamespace(url="postgresql://db/service"))
    monkeypatch.setattr(seed_module, "settings", SimpleNamespace(is_local_dev=True))
    assert seed_module._is_seed_enabled() is True

    monkeypatch.setattr(seed_module, "settings", SimpleNamespace(is_local_dev=False))
    assert seed_module._is_seed_enabled() is False


def test_session_quote_identifier_validation():
    assert session_module._quote_identifier("search_schema") == '"search_schema"'
    with pytest.raises(ValueError, match="Invalid database schema name"):
        session_module._quote_identifier("search-schema;drop")


def test_performance_helpers_cover_skipped_paths():
    sample = [10, 20, 30, 40, 50]
    assert perf_module._p(sample, 95) >= 10

    fake_use_case = SimpleNamespace(execute=lambda _q: {"ok": True})
    perf_module.TestCriteriosDeAceptacion().test_ca1_p95_bajo_800ms_carga_normal(fake_use_case)

    def _factory():
        return lambda _query: {"ok": True}

    perf_module.TestCriteriosDeAceptacion().test_ca2_100_concurrentes_p95_800ms_p99_1200ms(_factory)
    perf_module.TestCriteriosDeAceptacion().test_ca2_tasa_de_error_menor_1_porciento(_factory)
