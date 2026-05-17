"""Tests for seasonal pricing overrides applied in /properties/search."""
from datetime import date

from fastapi.testclient import TestClient
from sqlmodel import Session

from adapters.models.property_seasonal_price import PropertySeasonalPrice
from core.config import settings
from core.security import build_pricing_signature, canonicalize_pricing_payload
from db.seed import RENAISSANCE_ESTATE_ID


def _signed_seasonal_row(
    *,
    property_id,
    season_start: date,
    season_end: date,
    price_per_night: float,
    currency: str = "COP",
    tax_rate: float = 0.0,
    cleaning_fee: float = 0.0,
) -> PropertySeasonalPrice:
    canonical = canonicalize_pricing_payload(
        property_id=str(property_id),
        season_start=season_start.isoformat(),
        season_end=season_end.isoformat(),
        price_per_night=price_per_night,
        currency=currency,
        tax_rate=tax_rate,
        cleaning_fee=cleaning_fee,
    )
    signature = build_pricing_signature(canonical, settings.pricing_integrity_secret)
    return PropertySeasonalPrice(
        property_id=property_id,
        season_start=season_start,
        season_end=season_end,
        price_per_night=price_per_night,
        currency=currency,
        tax_rate=tax_rate,
        cleaning_fee=cleaning_fee,
        signature_hash=signature,
    )


def test_search_picks_lowest_overlapping_seasonal_price(
    client: TestClient, session: Session
):
    """When multiple valid seasonal rules cover the requested range, the cheapest wins."""
    rows = [
        _signed_seasonal_row(
            property_id=RENAISSANCE_ESTATE_ID,
            season_start=date(2026, 6, 1),
            season_end=date(2026, 9, 30),
            price_per_night=400.0,
        ),
        _signed_seasonal_row(
            property_id=RENAISSANCE_ESTATE_ID,
            season_start=date(2026, 5, 1),
            season_end=date(2026, 12, 31),
            price_per_night=200.0,  # cheapest -> wins
        ),
        _signed_seasonal_row(
            property_id=RENAISSANCE_ESTATE_ID,
            season_start=date(2026, 7, 1),
            season_end=date(2026, 8, 31),
            price_per_night=350.0,
        ),
    ]
    for row in rows:
        session.add(row)
    session.commit()

    response = client.get(
        "/api/v1/properties/search",
        params={
            "ids": str(RENAISSANCE_ESTATE_ID),
            "check_in": "2026-07-15",
            "check_out": "2026-07-20",
        },
    )
    assert response.status_code == 200
    items = response.json()["items"]
    target = next(
        item for item in items if item["id"] == str(RENAISSANCE_ESTATE_ID)
    )
    assert target["price_per_night"] == 200.0


def test_search_skips_locked_seasonal_rules(client: TestClient, session: Session):
    locked = _signed_seasonal_row(
        property_id=RENAISSANCE_ESTATE_ID,
        season_start=date(2026, 6, 1),
        season_end=date(2026, 8, 31),
        price_per_night=10.0,
    )
    locked.integrity_locked = True
    session.add(locked)
    session.commit()

    response = client.get(
        "/api/v1/properties/search",
        params={
            "ids": str(RENAISSANCE_ESTATE_ID),
            "check_in": "2026-07-01",
            "check_out": "2026-07-10",
        },
    )
    assert response.status_code == 200
    items = response.json()["items"]
    target = next(
        item for item in items if item["id"] == str(RENAISSANCE_ESTATE_ID)
    )
    # Locked row must not override the base price.
    assert target["price_per_night"] != 10.0


def test_search_rejects_partial_date_range(client: TestClient):
    response = client.get(
        "/api/v1/properties/search", params={"check_in": "2026-07-15"}
    )
    assert response.status_code == 400
    assert "check_in" in response.json()["detail"]


def test_search_rejects_inverted_date_range(client: TestClient):
    response = client.get(
        "/api/v1/properties/search",
        params={"check_in": "2026-07-20", "check_out": "2026-07-15"},
    )
    assert response.status_code == 400
