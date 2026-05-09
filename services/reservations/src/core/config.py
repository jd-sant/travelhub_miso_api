import os
from functools import lru_cache


class Settings:
    @property
    def environment(self) -> str:
        return os.getenv("ENV", os.getenv("APP_ENV", "development")).lower()

    @property
    def jwt_secret_key(self) -> str:
        value = os.getenv("JWT_SECRET_KEY")
        if value:
            return value
        if self.environment not in ("development", "dev", "test", "local"):
            raise RuntimeError(
                "JWT_SECRET_KEY debe estar configurado en entornos de producción."
            )
        return "travelhub-jwt-secret-change-in-prod"

    @property
    def jwt_algorithm(self) -> str:
        return os.getenv("JWT_ALGORITHM", "HS256")

    @property
    def allowed_cors_origins(self) -> list[str]:
        raw = os.getenv("ALLOWED_CORS_ORIGIN", "http://localhost:3000,http://127.0.0.1:3000")
        return [o.strip() for o in raw.split(",") if o.strip()]

    @property
    def is_local_dev(self) -> bool:
        env = os.getenv("ENV", os.getenv("APP_ENV", "development")).lower()
        return env in ("development", "dev", "test", "local")

    @property
    def reservation_scheduler_enabled(self) -> bool:
        return os.getenv("RESERVATION_SCHEDULER_ENABLED", "false").lower() == "true"

    @property
    def reservation_scheduler_delay_minutes(self) -> int:
        return int(os.getenv("RESERVATION_SCHEDULER_DELAY_MINUTES", "15"))

    @property
    def aws_region(self) -> str:
        return os.getenv("AWS_REGION", "us-east-1")

    @property
    def lambda_arn(self) -> str:
        return os.getenv("LAMBDA_ARN", "")

    @property
    def scheduler_role_arn(self) -> str:
        return os.getenv("SCHEDULER_ROLE_ARN", "")

    @property
    def api_base_url(self) -> str:
        return os.getenv("API_BASE_URL", "")

    @property
    def scheduler_group_name(self) -> str:
        return os.getenv("SCHEDULER_GROUP_NAME", "default")

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
        return os.getenv("DB_SCHEMA", "reservations_schema")

    @property
    def database_url(self) -> str:
        url = os.getenv("DATABASE_URL")
        if url:
            return url

        if self.environment in ("development", "dev", "test", "local"):
            return os.getenv("SQLITE_DATABASE_URL", "sqlite:///./reservations.db")

        return (
            f"postgresql://{self.rds_username}:{self.rds_password}"
            f"@{self.rds_hostname}:{self.rds_port}/{self.rds_db_name}?client_encoding=utf8"
        )

    @property
    def db_echo(self) -> bool:
        return os.getenv("DB_ECHO", "False").lower() == "true"

    @property
    def properties_service_url(self) -> str:
        return os.getenv("PROPERTIES_SERVICE_URL", "http://localhost:8005").rstrip("/")

    @property
    def users_service_url(self) -> str:
        return os.getenv("USERS_SERVICE_URL", "http://localhost:8000").rstrip("/")

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
    def payments_service_url(self) -> str:
        return os.getenv("PAYMENTS_SERVICE_URL", "http://payments:8000").rstrip("/")

    @property
    def search_service_url(self) -> str:
        return os.getenv("SEARCH_SERVICE_URL", "http://search:8000").rstrip("/")

    @property
    def notifications_service_url(self) -> str:
        return os.getenv("NOTIFICATIONS_SERVICE_URL", "http://notifications:8000").rstrip("/")

    @property
    def service_fee_rate(self) -> str:
        return os.getenv("TRAVELHUB_SERVICE_FEE_RATE", "0.08")

    def validate_scheduler_config(self) -> None:
        if not self.reservation_scheduler_enabled:
            return

        missing_values = []
        if not self.lambda_arn:
            missing_values.append("LAMBDA_ARN")
        if not self.scheduler_role_arn:
            missing_values.append("SCHEDULER_ROLE_ARN")
        if not self.api_base_url:
            missing_values.append("API_BASE_URL")

        if missing_values:
            raise RuntimeError(
                f"Scheduler enabled but missing configuration: {', '.join(missing_values)}"
            )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
