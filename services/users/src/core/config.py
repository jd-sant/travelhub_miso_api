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
        return os.getenv("DB_SCHEMA", "users_schema")

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
    def allowed_cors_origins(self) -> list[str]:
        raw_origins = os.getenv("ALLOWED_CORS_ORIGIN")
        if raw_origins:
            return [origin.strip() for origin in raw_origins.split(",") if origin.strip()]

        return ["http://localhost:3000", "http://127.0.0.1:3000"]

    @property
    def jwt_secret_key(self) -> str:
        return os.getenv("JWT_SECRET_KEY", "dev-secret-key-change-me")

    @property
    def jwt_algorithm(self) -> str:
        return os.getenv("JWT_ALGORITHM", "HS256")

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
