import os
from functools import lru_cache


class Settings:
    @property
    def environment(self) -> str:
        return os.getenv("ENV", os.getenv("APP_ENV", "development")).lower()

    @property
    def is_development(self) -> bool:
        return self.environment in ("development", "dev", "test", "local")

    @property
    def is_test(self) -> bool:
        return self.environment in ("test", "testing")

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
        return os.getenv("DB_SCHEMA", "search_schema")

    @property
    def database_url(self) -> str:
        url = os.getenv("DATABASE_URL")
        if url:
            return url

        if self.is_development:
            return os.getenv("SQLITE_DATABASE_URL", "sqlite:///./search.db")

        return (
            f"postgresql://{self.rds_username}:{self.rds_password}"
            f"@{self.rds_hostname}:{self.rds_port}/{self.rds_db_name}"
        )

    @property
    def db_echo(self) -> bool:
        return os.getenv("DB_ECHO", "False").lower() == "true"

    @property
    def cors_allow_origins(self) -> list[str]:
        raw_origins = os.getenv("CORS_ALLOW_ORIGINS")
        if raw_origins:
            return [origin.strip() for origin in raw_origins.split(",") if origin.strip()]

        if self.is_development:
            return [
                "http://localhost:3000",
                "http://127.0.0.1:3000",
                "http://localhost:5173",
                "http://127.0.0.1:5173",
            ]

        return []

    @property
    def cors_allow_credentials(self) -> bool:
        return os.getenv("CORS_ALLOW_CREDENTIALS", "false").lower() == "true"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()