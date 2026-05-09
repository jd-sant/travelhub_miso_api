import os
from functools import lru_cache


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
        return os.getenv("DB_SCHEMA", "security_schema")

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
    def allowed_cors_origins(self) -> list[str]:
        raw_origins = os.getenv("ALLOWED_CORS_ORIGIN")
        if raw_origins:
            return [origin.strip() for origin in raw_origins.split(",") if origin.strip()]

        return ["http://localhost:3000", "http://127.0.0.1:3000"]

    @property
    def jwt_secret_key(self) -> str:
        value = os.getenv("JWT_SECRET_KEY")
        if value:
            return value
        env = os.getenv("ENV", os.getenv("APP_ENV", "development")).lower()
        if env not in ("development", "dev", "test"):
            raise RuntimeError(
                "JWT_SECRET_KEY debe estar configurado en entornos de producción."
            )
        return "dev-secret-key-change-me"

    @property
    def jwt_algorithm(self) -> str:
        return os.getenv("JWT_ALGORITHM", "HS256")

    @property
    def jwt_expiration_minutes(self) -> int:
        return int(os.getenv("JWT_EXPIRATION_MINUTES", "30"))

    @property
    def otp_expiry_minutes(self) -> int:
        return int(os.getenv("OTP_EXPIRY_MINUTES", "5"))

    @property
    def otp_max_attempts(self) -> int:
        return int(os.getenv("OTP_MAX_ATTEMPTS", "3"))

    @property
    def account_lock_minutes(self) -> int:
        return int(os.getenv("ACCOUNT_LOCK_MINUTES", "15"))

    @property
    def ip_block_threshold(self) -> int:
        return int(os.getenv("IP_BLOCK_THRESHOLD", "10"))

    @property
    def ip_block_window_minutes(self) -> int:
        return int(os.getenv("IP_BLOCK_WINDOW_MINUTES", "5"))

    @property
    def users_service_url(self) -> str:
        return os.getenv("USERS_SERVICE_URL", "http://localhost:8000")

    @property
    def internal_api_key(self) -> str:
        value = os.getenv("INTERNAL_API_KEY")
        if value:
            return value
        env = os.getenv("ENV", os.getenv("APP_ENV", "development")).lower()
        if env not in ("development", "dev", "test"):
            raise RuntimeError(
                "INTERNAL_API_KEY debe estar configurado en entornos de producción."
            )
        return "dev-internal-key-change-me"

    @property
    def demo_seed_enabled(self) -> bool:
        return os.getenv("DEMO_SEED_ENABLED", "false").lower() == "true"

    @property
    def demo_hotel_emails(self) -> set[str]:
        raw = os.getenv(
            "DEMO_HOTEL_EMAILS",
            "hotel-a@travelhub.demo,hotel-b@travelhub.demo",
        )
        return {item.strip().lower() for item in raw.split(",") if item.strip()}

    @property
    def demo_otp_code(self) -> str:
        return os.getenv("DEMO_OTP_CODE", "000000")

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


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
