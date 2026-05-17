from uuid import uuid4

from adapters.services.users_client import UsersServiceClient


def test_users_client_sends_tls_header(monkeypatch):
    captured: dict = {}

    class FakeResponse:
        status_code = 200

        @staticmethod
        def json():
            return [{"id": str(uuid4()), "email": "ada@example.com"}]

    def fake_post(url, json, headers, timeout):
        captured["url"] = url
        captured["json"] = json
        captured["headers"] = headers
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr("adapters.services.users_client.httpx.post", fake_post)

    client = UsersServiceClient(base_url="https://users.example.com", timeout=7.5)
    result = client.list_by_ids([uuid4()])

    assert result
    assert captured["url"] == "https://users.example.com/api/v1/internal/users/by-ids"
    assert captured["headers"]["X-Internal-Api-Key"]
    assert captured["headers"]["X-Forwarded-Proto"] == "https"
    assert captured["timeout"] == 7.5
