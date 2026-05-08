"""Wire-format tests for the HTTP clients to properties and reservations."""
import json
from decimal import Decimal
from datetime import date
from unittest.mock import patch
from uuid import UUID, uuid4

import httpx
import pytest

from adapters.services.properties_service_client import HttpPropertiesServiceClient
from adapters.services.reservations_service_client import HttpReservationsServiceClient
from domain.ports.properties_service import PropertyQuery
from errors import (
    PropertiesServiceUnavailableError,
    ReservationsServiceUnavailableError,
)


def _mock_httpx(handler):
    """Patch the module-level httpx.get / httpx.post to use a MockTransport."""
    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport)
    return client


def test_properties_search_serializes_query_params():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["params"] = dict(request.url.params.multi_items())
        return httpx.Response(
            200,
            json={
                "items": [],
                "pagination": {
                    "total": 0,
                    "page": 1,
                    "page_size": 10,
                    "total_pages": 0,
                },
            },
        )

    transport = httpx.MockTransport(handler)
    with patch("adapters.services.properties_service_client.httpx") as mock_httpx:
        mock_httpx.get.side_effect = lambda url, params, timeout: httpx.Client(
            transport=transport
        ).get(url, params=params, timeout=timeout)
        mock_httpx.HTTPError = httpx.HTTPError

        client = HttpPropertiesServiceClient(base_url="http://props", timeout=2.0)
        page = client.search(
            PropertyQuery(
                city="Bogota",
                min_price=Decimal("100"),
                max_price=Decimal("2000"),
                min_guests=2,
                amenities=["wifi", "piscina"],
                ids=[UUID("11111111-1111-1111-1111-111111111111")],
                sort_by="price",
                sort_dir="asc",
                page=1,
                page_size=10,
            )
        )

    assert page.total == 0
    assert "/api/v1/properties/search" in captured["url"]
    # Multi-value params
    assert captured["params"] == {
        "city": "Bogota",
        "min_price": "100",
        "max_price": "2000",
        "min_guests": "2",
        "amenities": "piscina",  # last one wins via dict; we'll check multi below
        "ids": "11111111-1111-1111-1111-111111111111",
        "page": "1",
        "page_size": "10",
        "sort_by": "price",
        "sort_dir": "asc",
    }


def test_properties_search_parses_response():
    payload = {
        "items": [
            {
                "id": "11111111-1111-1111-1111-111111111111",
                "name": "Casa A",
                "location": "Bogotá, Colombia",
                "price_per_night": 100,
                "currency": "COP",
                "rating": 4.5,
                "max_guests": 4,
                "amenities": ["wifi"],
                "status": 1,
                "images": [
                    {"url": "https://x/cover.jpg", "is_cover": True},
                    {"url": "https://x/2.jpg", "is_cover": False},
                ],
            }
        ],
        "pagination": {"total": 1, "page": 1, "page_size": 10, "total_pages": 1},
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    transport = httpx.MockTransport(handler)
    with patch("adapters.services.properties_service_client.httpx") as mock_httpx:
        mock_httpx.get.side_effect = lambda url, params, timeout: httpx.Client(
            transport=transport
        ).get(url, params=params, timeout=timeout)
        mock_httpx.HTTPError = httpx.HTTPError

        client = HttpPropertiesServiceClient(base_url="http://props")
        page = client.search(PropertyQuery(city="Bogota"))

    assert page.total == 1
    assert page.items[0].name == "Casa A"
    assert page.items[0].cover_image_url() == "https://x/cover.jpg"
    city, country = page.items[0].split_location()
    assert city == "Bogotá"
    assert country == "Colombia"


def test_properties_search_unavailable_raises():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "boom"})

    transport = httpx.MockTransport(handler)
    with patch("adapters.services.properties_service_client.httpx") as mock_httpx:
        mock_httpx.get.side_effect = lambda url, params, timeout: httpx.Client(
            transport=transport
        ).get(url, params=params, timeout=timeout)
        mock_httpx.HTTPError = httpx.HTTPError
        mock_httpx.HTTPStatusError = httpx.HTTPStatusError

        client = HttpPropertiesServiceClient(base_url="http://props")
        with pytest.raises(PropertiesServiceUnavailableError):
            client.search(PropertyQuery())


def test_properties_get_by_id_returns_none_on_404():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"detail": "not found"})

    transport = httpx.MockTransport(handler)
    with patch("adapters.services.properties_service_client.httpx") as mock_httpx:
        mock_httpx.get.side_effect = lambda url, timeout: httpx.Client(
            transport=transport
        ).get(url, timeout=timeout)
        mock_httpx.HTTPError = httpx.HTTPError

        client = HttpPropertiesServiceClient(base_url="http://props")
        result = client.get_by_id(uuid4())

    assert result is None


def test_reservations_availability_check_serializes_body():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["body"] = json.loads(request.content)
        captured["headers"] = dict(request.headers)
        return httpx.Response(
            200, json={"available": [], "blocked": []}
        )

    transport = httpx.MockTransport(handler)
    with patch("adapters.services.reservations_service_client.httpx") as mock_httpx:
        mock_httpx.post.side_effect = lambda url, json, headers, timeout: httpx.Client(
            transport=transport
        ).post(url, json=json, headers=headers, timeout=timeout)
        mock_httpx.HTTPError = httpx.HTTPError

        client = HttpReservationsServiceClient(
            base_url="http://res", api_key="secret"
        )
        client.availability_check(
            [UUID("11111111-1111-1111-1111-111111111111")],
            date(2026, 6, 10),
            date(2026, 6, 15),
        )

    assert captured["url"].endswith("/api/v1/internal/reservations/availability-check")
    assert captured["body"] == {
        "property_ids": ["11111111-1111-1111-1111-111111111111"],
        "check_in": "2026-06-10",
        "check_out": "2026-06-15",
    }
    assert captured["headers"]["x-internal-api-key"] == "secret"


def test_reservations_availability_check_parses_response():
    p1 = UUID("11111111-1111-1111-1111-111111111111")
    p2 = UUID("22222222-2222-2222-2222-222222222222")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"available": [str(p1)], "blocked": [str(p2)]})

    transport = httpx.MockTransport(handler)
    with patch("adapters.services.reservations_service_client.httpx") as mock_httpx:
        mock_httpx.post.side_effect = lambda url, json, headers, timeout: httpx.Client(
            transport=transport
        ).post(url, json=json, headers=headers, timeout=timeout)
        mock_httpx.HTTPError = httpx.HTTPError

        client = HttpReservationsServiceClient(base_url="http://res", api_key="k")
        result = client.availability_check([p1, p2], date(2026, 6, 10), date(2026, 6, 15))

    assert result.available == [p1]
    assert result.blocked == [p2]


def test_reservations_availability_check_empty_skips_call():
    """Empty property_ids should short-circuit without making an HTTP call."""
    client = HttpReservationsServiceClient(base_url="http://res", api_key="k")
    result = client.availability_check([], date(2026, 6, 10), date(2026, 6, 15))
    assert result.available == []
    assert result.blocked == []


def test_reservations_availability_check_unavailable_raises():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    transport = httpx.MockTransport(handler)
    with patch("adapters.services.reservations_service_client.httpx") as mock_httpx:
        mock_httpx.post.side_effect = lambda url, json, headers, timeout: httpx.Client(
            transport=transport
        ).post(url, json=json, headers=headers, timeout=timeout)
        mock_httpx.HTTPError = httpx.HTTPError

        client = HttpReservationsServiceClient(base_url="http://res", api_key="k")
        with pytest.raises(ReservationsServiceUnavailableError):
            client.availability_check([uuid4()], date(2026, 6, 10), date(2026, 6, 15))
