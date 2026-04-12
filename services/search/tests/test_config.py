from core.config import Settings


class TestSearchSettings:
    def test_test_environment_is_not_development(self, monkeypatch):
        monkeypatch.setenv("ENV", "test")
        settings = Settings()

        assert settings.is_test is True
        assert settings.is_development is False
        assert settings.is_local_dev is False

    def test_local_dev_environment_enables_dev_features(self, monkeypatch):
        monkeypatch.setenv("ENV", "local")
        monkeypatch.delenv("DATABASE_URL", raising=False)
        monkeypatch.delenv("ALLOWED_CORS_ORIGIN", raising=False)
        settings = Settings()

        assert settings.is_development is False
        assert settings.is_local_dev is True
        assert settings.database_url == "sqlite:///./search.db"
        assert "http://localhost:3000" in settings.cors_allow_origins

    def test_allowed_cors_origin_env_is_used_when_present(self, monkeypatch):
        monkeypatch.setenv("ALLOWED_CORS_ORIGIN", "http://example.com,http://localhost:3000")
        settings = Settings()

        assert settings.cors_allow_origins == ["http://example.com", "http://localhost:3000"]
