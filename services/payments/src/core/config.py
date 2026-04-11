import os
from functools import lru_cache

from pydantic import SecretStr


class Settings:
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
        return os.getenv("DB_SCHEMA", "payments_schema")

    @property
    def database_url(self) -> str:
        url = os.getenv("DATABASE_URL")
        if url:
            return url
        return (
            f"postgresql://{self.rds_username}:{self.rds_password}"
            f"@{self.rds_hostname}:{self.rds_port}/{self.rds_db_name}"
        )

    @property
    def db_echo(self) -> bool:
        return os.getenv("DB_ECHO", "False").lower() == "true"

    @property
    def payment_provider(self) -> str:
        value = os.getenv("PAYMENT_PROVIDER")
        return (value or "fake_stripe").strip() or "fake_stripe"

    @property
    def stripe_secret_key(self) -> SecretStr:
        return SecretStr(os.getenv("STRIPE_SECRET_KEY", ""))

    @property
    def stripe_publishable_key(self) -> str:
        return os.getenv("STRIPE_PUBLISHABLE_KEY", "")

    @property
    def stripe_webhook_secret(self) -> SecretStr:
        return SecretStr(os.getenv("STRIPE_WEBHOOK_SECRET", ""))

    @property
    def stripe_enabled(self) -> bool:
        return (
            self.payment_provider == "stripe_test"
            and self.stripe_secret_key.get_secret_value().startswith("sk_test_")
            and self.stripe_publishable_key.startswith("pk_test_")
        )

    @property
    def payment_duplicate_window_seconds(self) -> int:
        return int(os.getenv("PAYMENT_DUPLICATE_WINDOW_SECONDS", "2"))

    @property
    def payment_integrity_secret(self) -> str:
        value = os.getenv("PAYMENT_INTEGRITY_SECRET")
        if value:
            return value
        env = os.getenv("ENV", os.getenv("APP_ENV", "development")).lower()
        if env not in ("development", "dev", "test"):
            raise RuntimeError(
                "PAYMENT_INTEGRITY_SECRET debe estar configurado en entornos de produccion."
            )
        return "dev-payments-secret-change-me"

    @property
    def enforce_tls_header(self) -> bool:
        return os.getenv("ENFORCE_TLS_HEADER", "True").lower() == "true"

    @property
    def skip_db_init_on_startup(self) -> bool:
        return os.getenv("SKIP_DB_INIT_ON_STARTUP", "False").lower() == "true"

    @property
    def allowed_cors_origins(self) -> list[str]:
        raw = os.getenv(
            "ALLOWED_CORS_ORIGINS",
            "http://localhost:3000,http://127.0.0.1:3000",
        )
        return [origin.strip() for origin in raw.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
