"""HTTP client for the security service.

Properties no longer holds the JWT secret; it delegates token validation to the
security service via POST /api/v1/auth/validate-token. See plan
`docs/plans/necesito-que-hagamos-un-memoized-clarke.md` for context.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from uuid import UUID

import httpx

from core.config import settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TokenClaims:
    user_id: UUID
    email: str
    role: str


class SecurityClient:
    def __init__(self, base_url: str | None = None, timeout_seconds: float = 1.5):
        self._base_url = (base_url or settings.security_service_url).rstrip("/")
        self._timeout = timeout_seconds

    def validate_token(self, token: str) -> TokenClaims | None:
        url = f"{self._base_url}/api/v1/auth/validate-token"
        try:
            response = httpx.post(url, json={"token": token}, timeout=self._timeout)
        except httpx.TimeoutException:
            logger.warning("security.validate_token timeout url=%s", url)
            return None
        except httpx.HTTPError as exc:
            logger.warning("security.validate_token http error: %s", exc)
            return None

        if response.status_code != 200:
            logger.info(
                "security.validate_token rejected token status=%s",
                response.status_code,
            )
            return None

        try:
            data = response.json()
            return TokenClaims(
                user_id=UUID(str(data["user_id"])),
                email=str(data["email"]),
                role=str(data["role"]),
            )
        except (KeyError, ValueError, TypeError) as exc:
            logger.warning("security.validate_token malformed response: %s", exc)
            return None
