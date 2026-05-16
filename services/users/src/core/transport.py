from fastapi import HTTPException, Request, status

from core.config import settings


def assert_secure_transport(request: Request) -> None:
    if (
        settings.enforce_tls_header
        and settings.app_env not in ("development", "dev", "test")
        and request.headers.get("X-Forwarded-Proto") != "https"
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="TLS 1.2+ is required for PII requests",
        )
