import os
from functools import lru_cache
from urllib.parse import urlparse


class Settings:
    @property
    def is_local_dev(self) -> bool:
        env = os.getenv("ENV", os.getenv("APP_ENV", "development")).lower()
        return env in ("development", "dev", "test", "local")

    @property
    def internal_api_key(self) -> str:
        value = os.getenv("INTERNAL_API_KEY")
        if value:
            return value
        if not self.is_local_dev:
            raise RuntimeError(
                "INTERNAL_API_KEY debe estar configurado en entornos de producción."
            )
        return "dev-internal-key-change-me"

    @property
    def rds_hostname(self) -> str:
        return os.getenv("RDS_HOSTNAME", "localhost")

    @property
    def rds_port(self) -> str:
        return os.getenv("RDS_PORT", "5432")

    @property
    def rds_username(self) -> str:
        return os.getenv("RDS_USERNAME", "travelhub_user")

    @property
    def rds_password(self) -> str:
        return os.getenv("RDS_PASSWORD", "travelhub_pass")

    @property
    def rds_db_name(self) -> str:
        return os.getenv("RDS_DB_NAME", "travelhub")

    @property
    def db_schema(self) -> str:
        return os.getenv("DB_SCHEMA", "properties_schema")

    @property
    def db_echo(self) -> bool:
        return os.getenv("DB_ECHO", "False").lower() == "true"

    @property
    def seed_demo_data(self) -> bool:
        value = os.getenv("SEED_DEMO_DATA")
        if value is None:
            return self.is_local_dev
        return value.lower() == "true"

    @property
    def allowed_cors_origins(self) -> list[str]:
        raw_origins = os.getenv("ALLOWED_CORS_ORIGIN")
        if raw_origins:
            return [origin.strip() for origin in raw_origins.split(",") if origin.strip()]

        return ["http://localhost:3000", "http://127.0.0.1:3000"]

    @property
    def database_url(self) -> str:
        return f"postgresql://{self.rds_username}:{self.rds_password}@{self.rds_hostname}:{self.rds_port}/{self.rds_db_name}"

    @property
    def redis_host(self) -> str:
        return os.getenv("REDIS_HOST", "localhost")

    @property
    def redis_port(self) -> int:
        return int(os.getenv("REDIS_PORT", "6379"))

    @property
    def redis_db(self) -> int:
        return int(os.getenv("REDIS_DB", "0"))

    @property
    def redis_cache_enabled(self) -> bool:
        return os.getenv("REDIS_CACHE_ENABLED", "false").lower() == "true"

    @property
    def redis_cache_ttl_seconds(self) -> int:
        return int(os.getenv("REDIS_CACHE_TTL_SECONDS", "300"))

    @property
    def redis_connection_pool_size(self) -> int:
        return int(os.getenv("REDIS_CONNECTION_POOL_SIZE", "20"))

    @property
    def asset_cdn_base_url(self) -> str | None:
        value = os.getenv("ASSET_CDN_BASE_URL", "").strip()
        return value.rstrip("/") if value else None

    @property
    def asset_cdn_enabled(self) -> bool:
        base_url = self.asset_cdn_base_url
        if not base_url:
            return False
        parsed = urlparse(base_url)
        return bool(parsed.scheme and parsed.netloc)

    @property
    def pricing_integrity_secret(self) -> str:
        value = os.getenv("PRICING_INTEGRITY_SECRET")
        if value:
            return value
        if not self.is_local_dev:
            raise RuntimeError(
                "PRICING_INTEGRITY_SECRET debe estar configurado en entornos de producción."
            )
        return "dev-pricing-secret-change-me"

    @property
    def pricing_signature_algo(self) -> str:
        return os.getenv("PRICING_SIGNATURE_ALGO", "HMAC-SHA256")

    @property
    def jwt_secret_key(self) -> str:
        value = os.getenv("JWT_SECRET_KEY")
        if value:
            return value
        if not self.is_local_dev:
            raise RuntimeError(
                "JWT_SECRET_KEY debe estar configurado en entornos de producción."
            )
        return "travelhub-jwt-secret-change-in-prod"

    @property
    def jwt_algorithm(self) -> str:
        return os.getenv("JWT_ALGORITHM", "HS256")

    @property
    def search_service_url(self) -> str:
        return os.getenv("SEARCH_SERVICE_URL", "http://search:8000").rstrip("/")

    @property
    def internal_api_key(self) -> str:
        value = os.getenv("INTERNAL_API_KEY")
        if value:
            return value
        if not self.is_local_dev:
            raise RuntimeError(
                "INTERNAL_API_KEY debe estar configurado en entornos de producción."
            )
        return "dev-internal-key-change-me"

    def load(self):
        pass


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
