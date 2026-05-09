from unittest.mock import patch
from uuid import UUID

import httpx
import pytest

from adapters.services.properties_client import PropertiesOwnershipClient
from errors import PricingServiceUnavailableError


def test_list_owned_property_ids_parses_successful_response():
    property_id = UUID("11111111-1111-1111-1111-111111111111")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/api/v1/properties")
        assert request.url.params["owner_id"] == "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
        return httpx.Response(200, json=[{"id": str(property_id)}])

    transport = httpx.MockTransport(handler)
    with patch("adapters.services.properties_client.httpx") as mock_httpx:
        mock_httpx.get.side_effect = lambda url, params, timeout: httpx.Client(
            transport=transport
        ).get(url, params=params, timeout=timeout)
        mock_httpx.HTTPError = httpx.HTTPError

        client = PropertiesOwnershipClient(base_url="http://properties", timeout=2.0)
        result = client.list_owned_property_ids(UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"))

    assert result == {property_id}


def test_list_owned_property_ids_maps_transport_errors_to_service_unavailable():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"detail": "temporarily unavailable"})

    transport = httpx.MockTransport(handler)
    with patch("adapters.services.properties_client.httpx") as mock_httpx:
        mock_httpx.get.side_effect = lambda url, params, timeout: httpx.Client(
            transport=transport
        ).get(url, params=params, timeout=timeout)
        mock_httpx.HTTPError = httpx.HTTPError

        client = PropertiesOwnershipClient(base_url="http://properties", timeout=2.0)
        with pytest.raises(PricingServiceUnavailableError):
            client.list_owned_property_ids(UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"))
