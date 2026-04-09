import os


class Settings:
    """Application settings"""
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql://user:password@localhost:5432/travelhub"
    )
    SERVICE_NAME: str = "properties"
    SERVICE_PORT: int = int(os.getenv("SERVICE_PORT", 8003))
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")


settings = Settings()
