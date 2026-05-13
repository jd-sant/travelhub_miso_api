from decimal import Decimal
from uuid import uuid4

import pytest

from domain.schemas.search import SearchQuery
from domain.use_cases.search_properties import SearchPropertiesUseCase

from conftest import make_property


BOG_NW_LAT = 4.78
BOG_NW_LNG = -74.12
BOG_SE_LAT = 4.55
BOG_SE_LNG = -74.02


def _bog_property(lat: float, lng: float, *, id=None, name: str = "Hotel Bogota"):
    return make_property(
        id=id or uuid4(),
        name=name,
        location="Bogota, Colombia",
        latitude=lat,
        longitude=lng,
        price_per_night=Decimal("250000"),
    )


# ── Router-level ──────────────────────────────────────────────────────────────


class TestSearchByBbox:
    def test_bbox_only_search_returns_items_within(self, client, fake_properties):
        in_bog = _bog_property(4.71, -74.07, name="In Bogota")
        outside = _bog_property(10.40, -75.51, name="In Cartagena")
        fake_properties.catalog = [in_bog, outside]

        response = client.get(
            "/api/v1/search",
            params={
                "guests": 2,
                "min_lat": BOG_SE_LAT,
                "max_lat": BOG_NW_LAT,
                "min_lng": BOG_NW_LNG,
                "max_lng": BOG_SE_LNG,
                "check_in": "2026-04-10",
                "check_out": "2026-04-12",
            },
        )
        assert response.status_code == 200
        items = response.json()["items"]
        ids = {i["id"] for i in items}
        assert str(in_bog.id) in ids
        assert str(outside.id) not in ids

    def test_bbox_response_carries_lat_lng_per_item(self, client, fake_properties):
        prop = _bog_property(4.71, -74.07)
        fake_properties.catalog = [prop]

        response = client.get(
            "/api/v1/search",
            params={
                "guests": 2,
                "min_lat": BOG_SE_LAT,
                "max_lat": BOG_NW_LAT,
                "min_lng": BOG_NW_LNG,
                "max_lng": BOG_SE_LNG,
                "check_in": "2026-04-10",
                "check_out": "2026-04-12",
            },
        )
        item = response.json()["items"][0]
        assert item["latitude"] == 4.71
        assert item["longitude"] == -74.07

    def test_bbox_without_dates_skips_availability_check(
        self, client, fake_properties, fake_reservations
    ):
        prop = _bog_property(4.71, -74.07)
        fake_properties.catalog = [prop]
        # Even if reservations would mark it blocked, it must still be returned because
        # availability is skipped when dates are absent.
        fake_reservations.blocked_ids = {prop.id}

        response = client.get(
            "/api/v1/search",
            params={
                "guests": 2,
                "min_lat": BOG_SE_LAT,
                "max_lat": BOG_NW_LAT,
                "min_lng": BOG_NW_LNG,
                "max_lng": BOG_SE_LNG,
            },
        )
        assert response.status_code == 200
        assert fake_reservations.last_call is None
        ids = {i["id"] for i in response.json()["items"]}
        assert str(prop.id) in ids

    def test_partial_bbox_returns_400(self, client):
        response = client.get(
            "/api/v1/search",
            params={
                "guests": 2,
                "min_lat": BOG_SE_LAT,
                "max_lat": BOG_NW_LAT,
                # missing min_lng, max_lng
                "check_in": "2026-04-10",
                "check_out": "2026-04-12",
            },
        )
        assert response.status_code == 400

    def test_inverted_bbox_returns_400(self, client):
        response = client.get(
            "/api/v1/search",
            params={
                "guests": 2,
                "min_lat": BOG_NW_LAT,  # min > max
                "max_lat": BOG_SE_LAT,
                "min_lng": BOG_NW_LNG,
                "max_lng": BOG_SE_LNG,
                "check_in": "2026-04-10",
                "check_out": "2026-04-12",
            },
        )
        assert response.status_code == 400

    def test_out_of_range_bbox_returns_422(self, client):
        response = client.get(
            "/api/v1/search",
            params={
                "guests": 2,
                "min_lat": -91.0,
                "max_lat": BOG_NW_LAT,
                "min_lng": BOG_NW_LNG,
                "max_lng": BOG_SE_LNG,
                "check_in": "2026-04-10",
                "check_out": "2026-04-12",
            },
        )
        assert response.status_code == 422

    def test_bbox_empty_zone_emits_TRY_OTHER_AREA(self, client, fake_properties):
        fake_properties.catalog = []
        response = client.get(
            "/api/v1/search",
            params={
                "guests": 2,
                "min_lat": BOG_SE_LAT,
                "max_lat": BOG_NW_LAT,
                "min_lng": BOG_NW_LNG,
                "max_lng": BOG_SE_LNG,
            },
        )
        assert response.status_code == 200
        codes = {s["code"] for s in response.json()["empty_state"]}
        assert "TRY_OTHER_AREA" in codes


# ── Cache key ────────────────────────────────────────────────────────────────


class TestCacheKeyWithBbox:
    @pytest.mark.parametrize(
        "a, b",
        [
            (
                {"min_lat": 4.55, "max_lat": 4.78, "min_lng": -74.12, "max_lng": -74.02},
                {"min_lat": 6.20, "max_lat": 6.30, "min_lng": -75.60, "max_lng": -75.50},
            ),
            (
                {"city": "Bogota"},
                {"min_lat": 4.55, "max_lat": 4.78, "min_lng": -74.12, "max_lng": -74.02},
            ),
        ],
    )
    def test_distinct_queries_yield_distinct_keys(self, a, b):
        from datetime import date

        base = {"guests": 2, "check_in": date(2026, 4, 10), "check_out": date(2026, 4, 12)}
        key_a = SearchPropertiesUseCase._cache_key(SearchQuery(**base, **a))
        key_b = SearchPropertiesUseCase._cache_key(SearchQuery(**base, **b))
        assert key_a != key_b
