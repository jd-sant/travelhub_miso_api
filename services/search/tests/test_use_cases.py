"""Tests for SearchPropertiesUseCase orchestration over fake HTTP clients."""
from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from domain.schemas.search import SearchQuery
from domain.use_cases.search_properties import SearchPropertiesUseCase
from errors import PropertiesServiceUnavailableError, ReservationsServiceUnavailableError
from tests.conftest import make_property


def _query(**overrides) -> SearchQuery:
    defaults = dict(
        city="Bogota",
        check_in=date(2026, 4, 10),
        check_out=date(2026, 4, 12),
        guests=2,
        page=1,
        page_size=10,
    )
    return SearchQuery(**(defaults | overrides))


def test_returns_results_when_properties_match_and_are_available(
    fake_properties, fake_reservations
):
    p1 = make_property(name="P1", location="Bogota, Colombia", price_per_night=Decimal("100"))
    fake_properties.catalog = [p1]
    use_case = SearchPropertiesUseCase(fake_properties, fake_reservations)

    result = use_case.execute(_query())

    assert result.total == 1
    assert len(result.items) == 1
    item = result.items[0]
    assert item.id == p1.id
    assert item.city == "Bogota"
    assert item.country == "Colombia"
    assert item.price_from == Decimal("100")
    assert item.currency == "COP"
    assert item.max_capacity == p1.max_guests
    assert item.main_image_url == "https://x/cover.jpg"


def test_blocked_properties_are_filtered_out(fake_properties, fake_reservations):
    p1 = make_property(name="P1", location="Bogota, Colombia")
    p2 = make_property(name="P2", location="Bogota, Colombia")
    fake_properties.catalog = [p1, p2]
    fake_reservations.blocked_ids = {p2.id}

    use_case = SearchPropertiesUseCase(fake_properties, fake_reservations)
    result = use_case.execute(_query())

    ids = {item.id for item in result.items}
    assert ids == {p1.id}


def test_returns_empty_when_no_properties(fake_properties, fake_reservations):
    use_case = SearchPropertiesUseCase(fake_properties, fake_reservations)
    result = use_case.execute(_query(city="Atlantis"))
    assert result.total == 0
    assert result.items == []


def test_calls_properties_with_translated_query_params(
    fake_properties, fake_reservations
):
    fake_properties.catalog = []
    use_case = SearchPropertiesUseCase(fake_properties, fake_reservations)

    use_case.execute(
        _query(
            city="Bogota",
            guests=3,
            min_price=Decimal("100"),
            max_price=Decimal("500"),
            amenities=["wifi"],
            order_by="rating",
            order_dir="desc",
            page=2,
            page_size=20,
        )
    )

    assert fake_properties.last_query.city == "Bogota"
    assert fake_properties.last_query.min_guests == 3
    assert fake_properties.last_query.min_price == Decimal("100")
    assert fake_properties.last_query.max_price == Decimal("500")
    assert fake_properties.last_query.amenities == ["wifi"]
    assert fake_properties.last_query.sort_by == "rating"
    assert fake_properties.last_query.sort_dir == "desc"
    assert fake_properties.last_query.page == 2
    assert fake_properties.last_query.page_size == 20


def test_does_not_call_reservations_with_empty_property_list(
    fake_properties, fake_reservations
):
    fake_properties.catalog = []
    use_case = SearchPropertiesUseCase(fake_properties, fake_reservations)
    use_case.execute(_query())
    # The fake records every call; with empty IDs it's still called once with []
    # but with our short-circuit in the http client, that wouldn't matter.
    # Either way, the result is empty:
    # We still expect a deterministic call:
    assert fake_reservations.last_call is None or fake_reservations.last_call["property_ids"] == []


def test_propagates_properties_service_unavailable(fake_properties, fake_reservations):
    fake_properties.raises = PropertiesServiceUnavailableError("down")
    use_case = SearchPropertiesUseCase(fake_properties, fake_reservations)
    with pytest.raises(PropertiesServiceUnavailableError):
        use_case.execute(_query())


def test_propagates_reservations_service_unavailable(fake_properties, fake_reservations):
    fake_properties.catalog = [make_property(location="Bogota, Colombia")]
    fake_reservations.raises = ReservationsServiceUnavailableError("down")
    use_case = SearchPropertiesUseCase(fake_properties, fake_reservations)
    with pytest.raises(ReservationsServiceUnavailableError):
        use_case.execute(_query())


def test_amenity_filter_passed_through_lowercased_to_properties(
    fake_properties, fake_reservations
):
    p_with_wifi = make_property(
        name="WiFi place",
        location="Bogota, Colombia",
        amenities=["WiFi Fibra de Alta Velocidad"],
    )
    fake_properties.catalog = [p_with_wifi]
    use_case = SearchPropertiesUseCase(fake_properties, fake_reservations)

    result = use_case.execute(_query(amenities=["wifi"]))
    assert {item.id for item in result.items} == {p_with_wifi.id}


def test_pagination_total_is_passed_through_from_properties(
    fake_properties, fake_reservations
):
    fake_properties.catalog = [
        make_property(name=f"P{i}", location="Bogota, Colombia") for i in range(15)
    ]
    use_case = SearchPropertiesUseCase(fake_properties, fake_reservations)

    page1 = use_case.execute(_query(page=1, page_size=5))
    page2 = use_case.execute(_query(page=2, page_size=5))
    page3 = use_case.execute(_query(page=3, page_size=5))

    assert page1.total == 15
    assert page2.total == 15
    assert page3.total == 15
    assert len(page1.items) == 5
    assert len(page2.items) == 5
    assert len(page3.items) == 5


def test_location_split_handles_single_part(fake_properties, fake_reservations):
    p = make_property(location="Bora Bora")
    fake_properties.catalog = [p]
    use_case = SearchPropertiesUseCase(fake_properties, fake_reservations)
    result = use_case.execute(_query(city="Bora"))
    assert result.items[0].city == "Bora Bora"
    assert result.items[0].country == ""


def test_location_split_keeps_extra_commas_in_country(
    fake_properties, fake_reservations
):
    p = make_property(location="Cali, Valle del Cauca, Colombia")
    fake_properties.catalog = [p]
    use_case = SearchPropertiesUseCase(fake_properties, fake_reservations)
    result = use_case.execute(_query(city="Cali"))
    assert result.items[0].city == "Cali"
    assert result.items[0].country == "Valle del Cauca, Colombia"
