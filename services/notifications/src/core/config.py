import os
from functools import lru_cache
from urllib.parse import urlparse


class Settings:
    @property
    def app_env(self) -> str:
        return os.getenv("ENV", os.getenv("APP_ENV", "development")).lower()

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
        return os.getenv("DB_SCHEMA", "notifications_schema")

    @property
    def database_url(self) -> str:
        url = os.getenv("DATABASE_URL")
        if url:
            return url
        return (
            f"postgresql://{self.rds_username}:{self.rds_password}"
            f"@{self.rds_hostname}:{self.rds_port}/{self.rds_db_name}?client_encoding=utf8"
        )

    @property
    def db_echo(self) -> bool:
        return os.getenv("DB_ECHO", "False").lower() == "true"

    @property
    def smtp_host(self) -> str:
        return os.getenv("SMTP_HOST", "")

    @property
    def smtp_port(self) -> int:
        return int(os.getenv("SMTP_PORT", "587"))

    @property
    def smtp_user(self) -> str:
        return os.getenv("SMTP_USER", "")

    @property
    def smtp_password(self) -> str:
        return os.getenv("SMTP_PASSWORD", "")

    @property
    def smtp_from(self) -> str:
        return os.getenv("SMTP_FROM", "noreply@travelhub.com")

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

    @property
    def payments_service_url(self) -> str:
        value = os.getenv("PAYMENTS_SERVICE_URL", "http://payments:8000").rstrip("/")
        self._assert_internal_service_url(value, "PAYMENTS_SERVICE_URL")
        return value

    @property
    def users_service_url(self) -> str:
        value = os.getenv("USERS_SERVICE_URL", "http://users:8000").rstrip("/")
        self._assert_internal_service_url(value, "USERS_SERVICE_URL")
        return value

    @property
    def skip_db_init_on_startup(self) -> bool:
        return os.getenv("SKIP_DB_INIT_ON_STARTUP", "False").lower() == "true"

    @property
    def aws_region(self) -> str:
        return os.getenv("AWS_REGION", "us-east-1")

    @property
    def notifications_queue_url(self) -> str:
        return os.getenv("NOTIFICATIONS_QUEUE_URL", "").strip()

    @property
    def ses_from_address(self) -> str:
        return os.getenv("SES_FROM_ADDRESS", "").strip()

    @property
    def ses_region(self) -> str:
        return os.getenv("SES_REGION", self.aws_region)

    @property
    def service_mode(self) -> str:
        """api | worker. Controla el CMD del contenedor."""
        return os.getenv("SERVICE_MODE", "api").strip().lower()

    @property
    def sqs_poll_wait_seconds(self) -> int:
        return int(os.getenv("SQS_POLL_WAIT_SECONDS", "20"))

    @property
    def sqs_max_messages(self) -> int:
        return int(os.getenv("SQS_MAX_MESSAGES", "10"))

    def _assert_internal_service_url(self, value: str, variable_name: str) -> None:
        parsed = urlparse(value)
        if not parsed.scheme or not parsed.netloc:
            raise RuntimeError(f"{variable_name} debe ser una URL absoluta valida.")
        if self.app_env not in ("development", "dev", "test") and parsed.scheme != "https":
            raise RuntimeError(
                f"{variable_name} debe usar https en entornos no-dev."
            )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
