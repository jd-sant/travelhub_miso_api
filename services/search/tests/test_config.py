from core.config import Settings


class TestSearchSettings:
    def test_test_environment_is_not_development(self, monkeypatch):
        monkeypatch.setenv("ENV", "test")
        settings = Settings()

        assert settings.is_test is True
        assert settings.is_development is False
        assert settings.is_local_dev is False

    def test_local_dev_environment_flag(self, monkeypatch):
        monkeypatch.setenv("ENV", "local")
        monkeypatch.delenv("ALLOWED_CORS_ORIGIN", raising=False)
        settings = Settings()

        assert settings.is_development is False
        assert settings.is_local_dev is True
        assert "http://localhost:3000" in settings.cors_allow_origins

    def test_allowed_cors_origin_env_is_used_when_present(self, monkeypatch):
        monkeypatch.setenv("ALLOWED_CORS_ORIGIN", "http://example.com,http://localhost:3000")
        settings = Settings()

        assert settings.cors_allow_origins == ["http://example.com", "http://localhost:3000"]

    def test_service_urls_default_to_compose_hostnames(self, monkeypatch):
        monkeypatch.delenv("PROPERTIES_SERVICE_URL", raising=False)
        monkeypatch.delenv("RESERVATIONS_SERVICE_URL", raising=False)
        settings = Settings()

        assert settings.properties_service_url == "http://properties:8000"
        assert settings.reservations_service_url == "http://reservations:8000"

    def test_service_urls_strip_trailing_slash(self, monkeypatch):
        monkeypatch.setenv("PROPERTIES_SERVICE_URL", "http://props:9000/")
        monkeypatch.setenv("RESERVATIONS_SERVICE_URL", "http://res:9000///")
        settings = Settings()

        assert settings.properties_service_url == "http://props:9000"
        assert settings.reservations_service_url == "http://res:9000"

    def test_service_request_timeout_default(self, monkeypatch):
        monkeypatch.delenv("SERVICE_REQUEST_TIMEOUT", raising=False)
        settings = Settings()
        assert settings.service_request_timeout == 5.0
