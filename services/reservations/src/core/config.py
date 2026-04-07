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
        return os.getenv("DB_SCHEMA", "reservations_schema")

    @property
    def database_url(self) -> str:
        url = os.getenv("DATABASE_URL")
        if url:
            return url

        env = os.getenv("ENV", os.getenv("APP_ENV", "development")).lower()
        if env in ("development", "dev", "test", "local"):
            return os.getenv("SQLITE_DATABASE_URL", "sqlite:///./reservations.db")

        return (
            f"postgresql://{self.rds_username}:{self.rds_password}"
            f"@{self.rds_hostname}:{self.rds_port}/{self.rds_db_name}"
        )

    @property
    def db_echo(self) -> bool:
        return os.getenv("DB_ECHO", "False").lower() == "true"

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


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
