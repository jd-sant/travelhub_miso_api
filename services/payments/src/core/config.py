import os
from functools import lru_cache
from urllib.parse import urlparse

from pydantic import SecretStr


class Settings:
    @property
    def app_env(self) -> str:
        return os.getenv("ENV", os.getenv("APP_ENV", "development")).lower()

    @property
    def compliance_mode(self) -> bool:
        raw = os.getenv("PAYMENTS_COMPLIANCE_MODE")
        if raw is not None:
            return raw.lower() == "true"
        return self.app_env not in ("development", "dev", "test")

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
        provider = (value or "fake_stripe").strip() or "fake_stripe"
        if provider not in {"fake_stripe", "stripe_test"}:
            raise RuntimeError(
                "PAYMENT_PROVIDER debe ser uno de: fake_stripe, stripe_test."
            )
        if self.compliance_mode and provider != "stripe_test":
            raise RuntimeError(
                "PAYMENT_PROVIDER debe ser stripe_test cuando PAYMENTS_COMPLIANCE_MODE esta activo."
            )
        return provider

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
        enabled = (
            self.payment_provider == "stripe_test"
            and self.stripe_secret_key.get_secret_value().startswith("sk_test_")
            and self.stripe_publishable_key.startswith("pk_test_")
        )
        if self.compliance_mode and not enabled:
            raise RuntimeError(
                "Stripe test mode debe estar correctamente configurado cuando PAYMENTS_COMPLIANCE_MODE esta activo."
            )
        return enabled

    @property
    def payment_duplicate_window_seconds(self) -> int:
        return int(os.getenv("PAYMENT_DUPLICATE_WINDOW_SECONDS", "2"))

    @property
    def payment_integrity_secret(self) -> str:
        value = os.getenv("PAYMENT_INTEGRITY_SECRET")
        if value:
            return value
        if self.app_env not in ("development", "dev", "test"):
            raise RuntimeError(
                "PAYMENT_INTEGRITY_SECRET debe estar configurado en entornos de produccion."
            )
        return "dev-payments-secret-change-me"

    @property
    def payments_data_encryption_key(self) -> str:
        value = os.getenv("PAYMENTS_DATA_ENCRYPTION_KEY")
        if value:
            return value
        if self.compliance_mode:
            raise RuntimeError(
                "PAYMENTS_DATA_ENCRYPTION_KEY debe estar configurado cuando PAYMENTS_COMPLIANCE_MODE esta activo."
            )
        return "dev-payments-encryption-key-change-me"

    @property
    def enforce_tls_header(self) -> bool:
        return os.getenv("ENFORCE_TLS_HEADER", "True").lower() == "true"

    @property
    def skip_db_init_on_startup(self) -> bool:
        return os.getenv("SKIP_DB_INIT_ON_STARTUP", "False").lower() == "true"

    @property
    def allowed_cors_origins(self) -> list[str]:
        raw = os.getenv(
            "ALLOWED_CORS_ORIGIN",
            "http://localhost:3000,http://127.0.0.1:3000",
        )
        return [origin.strip() for origin in raw.split(",") if origin.strip()]

    @property
    def notifications_service_url(self) -> str:
        value = os.getenv("NOTIFICATIONS_SERVICE_URL", "").rstrip("/")
        if self.compliance_mode and not value:
            raise RuntimeError(
                "NOTIFICATIONS_SERVICE_URL debe estar configurado cuando PAYMENTS_COMPLIANCE_MODE esta activo."
            )
        self._assert_internal_service_url(value, "NOTIFICATIONS_SERVICE_URL")
        return value

    @property
    def reservations_service_url(self) -> str:
        value = os.getenv("RESERVATIONS_SERVICE_URL", "").rstrip("/")
        if self.compliance_mode and not value:
            raise RuntimeError(
                "RESERVATIONS_SERVICE_URL debe estar configurado cuando PAYMENTS_COMPLIANCE_MODE esta activo."
            )
        self._assert_internal_service_url(value, "RESERVATIONS_SERVICE_URL")
        return value

    @property
    def properties_service_url(self) -> str:
        value = os.getenv("PROPERTIES_SERVICE_URL", "").rstrip("/")
        if value:
            self._assert_internal_service_url(value, "PROPERTIES_SERVICE_URL")
        return value

    @property
    def reservation_confirmation_retry_base_seconds(self) -> int:
        value = int(os.getenv("RESERVATION_CONFIRMATION_RETRY_BASE_SECONDS", "30"))
        if value <= 0:
            raise RuntimeError("RESERVATION_CONFIRMATION_RETRY_BASE_SECONDS debe ser mayor a 0.")
        return value

    @property
    def reservation_confirmation_retry_max_backoff_seconds(self) -> int:
        value = int(os.getenv("RESERVATION_CONFIRMATION_RETRY_MAX_BACKOFF_SECONDS", "600"))
        if value <= 0:
            raise RuntimeError("RESERVATION_CONFIRMATION_RETRY_MAX_BACKOFF_SECONDS debe ser mayor a 0.")
        return value

    @property
    def reservation_confirmation_retry_max_attempts(self) -> int:
        value = int(os.getenv("RESERVATION_CONFIRMATION_RETRY_MAX_ATTEMPTS", "5"))
        if value <= 0:
            raise RuntimeError("RESERVATION_CONFIRMATION_RETRY_MAX_ATTEMPTS debe ser mayor a 0.")
        return value

    @property
    def reservation_confirmation_retry_batch_size(self) -> int:
        value = int(os.getenv("RESERVATION_CONFIRMATION_RETRY_BATCH_SIZE", "50"))
        if value <= 0:
            raise RuntimeError("RESERVATION_CONFIRMATION_RETRY_BATCH_SIZE debe ser mayor a 0.")
        return value

    @property
    def aws_region(self) -> str:
        return os.getenv("AWS_REGION", "us-east-1")

    @property
    def notifications_queue_url(self) -> str:
        return os.getenv("NOTIFICATIONS_QUEUE_URL", "").strip()

    @property
    def notifications_dispatch_mode(self) -> str:
        """sqs (default cuando hay queue url) | http (fallback legacy) | noop."""
        explicit = os.getenv("NOTIFICATIONS_DISPATCH_MODE", "").strip().lower()
        if explicit in {"sqs", "http", "noop"}:
            return explicit
        if self.notifications_queue_url:
            return "sqs"
        if self.notifications_service_url:
            return "http"
        return "noop"

    @property
    def default_cancellation_policy(self) -> str:
        return os.getenv(
            "DEFAULT_CANCELLATION_POLICY",
            "Cancelacion gratuita hasta 48 horas antes del check-in. Despues se cobra la primera noche.",
        )

    @property
    def default_tax_rate_by_currency(self) -> dict[str, float]:
        return {"COP": 0.19, "USD": 0.08, "MXN": 0.16, "EUR": 0.21, "BRL": 0.17}

    @property
    def refund_retry_base_seconds(self) -> int:
        value = int(os.getenv("REFUND_RETRY_BASE_SECONDS", "30"))
        if value <= 0:
            raise RuntimeError("REFUND_RETRY_BASE_SECONDS debe ser mayor a 0.")
        return value

    @property
    def refund_retry_max_backoff_seconds(self) -> int:
        value = int(os.getenv("REFUND_RETRY_MAX_BACKOFF_SECONDS", "600"))
        if value <= 0:
            raise RuntimeError("REFUND_RETRY_MAX_BACKOFF_SECONDS debe ser mayor a 0.")
        return value

    @property
    def refund_retry_max_attempts(self) -> int:
        value = int(os.getenv("REFUND_RETRY_MAX_ATTEMPTS", "5"))
        if value <= 0:
            raise RuntimeError("REFUND_RETRY_MAX_ATTEMPTS debe ser mayor a 0.")
        return value

    @property
    def refund_retry_batch_size(self) -> int:
        value = int(os.getenv("REFUND_RETRY_BATCH_SIZE", "50"))
        if value <= 0:
            raise RuntimeError("REFUND_RETRY_BATCH_SIZE debe ser mayor a 0.")
        return value

    @property
    def refund_sla_minutes(self) -> int:
        value = int(os.getenv("REFUND_SLA_MINUTES", "60"))
        if value <= 0:
            raise RuntimeError("REFUND_SLA_MINUTES debe ser mayor a 0.")
        return value

    @property
    def internal_api_key(self) -> str:
        value = os.getenv("INTERNAL_API_KEY")
        if value:
            return value
        if self.app_env not in ("development", "dev", "test"):
            raise RuntimeError(
                "INTERNAL_API_KEY debe estar configurado en entornos de produccion."
            )
        return "dev-internal-key-change-me"

    def _assert_internal_service_url(self, value: str, variable_name: str) -> None:
        if not value:
            return
        parsed = urlparse(value)
        if not parsed.scheme or not parsed.netloc:
            raise RuntimeError(f"{variable_name} debe ser una URL absoluta valida.")
        if self.compliance_mode and parsed.scheme != "https":
            raise RuntimeError(
                f"{variable_name} debe usar https cuando PAYMENTS_COMPLIANCE_MODE esta activo."
            )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
