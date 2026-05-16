from __future__ import annotations

import logging

import httpx

from core.config import settings

logger = logging.getLogger(__name__)


def invalidate_search_cache(
    base_url: str | None = None,
    api_key: str | None = None,
    timeout_seconds: float = 3.0,
) -> None:
    url = f"{(base_url or settings.search_service_url).rstrip('/')}/api/v1/search/internal/cache/invalidate"
    headers = {"X-API-Key": api_key or settings.internal_api_key}
    try:
        with httpx.Client(timeout=timeout_seconds) as client:
            response = client.post(url, headers=headers)
        if response.status_code >= 400:
            logger.warning(
                "search invalidation returned status=%s body=%s",
                response.status_code,
                response.text[:200],
            )
    except httpx.TimeoutException:
        logger.warning("search invalidation timeout url=%s", url)
    except httpx.HTTPError as exc:
        logger.warning("search invalidation http error: %s", exc)
