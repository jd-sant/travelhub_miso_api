import os
from functools import lru_cache

from core.privacy import load_residency_policies


class Settings:
    @property
    def app_env(self) -> str:
        return os.getenv("ENV", os.getenv("APP_ENV", "development")).lower()

    @property
    def privacy_compliance_mode(self) -> bool:
        raw = os.getenv("PRIVACY_COMPLIANCE_MODE")
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
    def demo_seed_enabled(self) -> bool:
        return os.getenv("DEMO_SEED_ENABLED", "false").lower() == "true"

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
    def users_pii_encryption_enabled(self) -> bool:
        raw = os.getenv("USERS_PII_ENCRYPTION_ENABLED")
        if raw is not None:
            return raw.lower() == "true"
        return self.privacy_compliance_mode

    @property
    def users_pii_encryption_key(self) -> str:
        value = os.getenv("USERS_PII_ENCRYPTION_KEY") or os.getenv("PII_DATA_ENCRYPTION_KEY")
        if value:
            return value
        if self.users_pii_encryption_enabled:
            raise RuntimeError(
                "USERS_PII_ENCRYPTION_KEY debe estar configurado para cifrar PII."
            )
        return "dev-users-pii-encryption-key-change-me"

    @property
    def users_email_lookup_hash_secret(self) -> str:
        value = os.getenv("USERS_EMAIL_LOOKUP_HASH_SECRET")
        if value:
            return value
        if self.privacy_compliance_mode:
            raise RuntimeError(
                "USERS_EMAIL_LOOKUP_HASH_SECRET debe estar configurado en modo de cumplimiento."
            )
        return "dev-users-email-lookup-hash-secret-change-me"

    @property
    def default_data_region(self) -> str:
        return os.getenv("DEFAULT_DATA_REGION", "aws-us-east-1")

    @property
    def data_residency_policies(self) -> dict[str, str]:
        return load_residency_policies(os.getenv("DATA_RESIDENCY_POLICIES"))

    @property
    def privacy_audit_enabled(self) -> bool:
        raw = os.getenv("PRIVACY_AUDIT_ENABLED")
        if raw is not None:
            return raw.lower() == "true"
        return self.privacy_compliance_mode

    @property
    def security_service_url(self) -> str:
        return os.getenv("SECURITY_SERVICE_URL", "http://security:8000").rstrip("/")

    @property
    def service_request_timeout(self) -> float:
        return float(os.getenv("SERVICE_REQUEST_TIMEOUT", "5.0"))

    @property
    def enforce_tls_header(self) -> bool:
        raw = os.getenv("ENFORCE_TLS_HEADER")
        if raw is not None:
            return raw.lower() == "true"
        return self.privacy_compliance_mode


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
