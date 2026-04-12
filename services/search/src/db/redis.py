import logging
import time
from threading import Lock
from typing import Optional

from redis import Redis, ConnectionPool
from redis.exceptions import RedisError

from core.config import settings

logger = logging.getLogger(__name__)

_pool: Optional[ConnectionPool] = None
_pool_lock = Lock()
_retry_interval_seconds = 5.0
_next_retry_at = 0.0


def _build_pool() -> Optional[ConnectionPool]:
    """Crea connection pool de Redis. Retorna None si está deshabilitado o falla."""
    if not settings.redis_cache_enabled:
        logger.info("Redis cache deshabilitado (REDIS_CACHE_ENABLED=false)")
        return None
    try:
        pool = ConnectionPool(
            host=settings.redis_host,
            port=settings.redis_port,
            db=settings.redis_db,
            max_connections=settings.redis_connection_pool_size,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
        Redis(connection_pool=pool).ping()
        logger.info(
            "Redis conectado: %s:%d/db%d",
            settings.redis_host,
            settings.redis_port,
            settings.redis_db,
        )
        return pool
    except RedisError as exc:
        logger.warning("Redis no disponible: %s. Búsquedas irán directo a BD.", exc)
        return None

def get_redis_client() -> Optional[Redis]:
    """
    Retorna cliente Redis listo para usar, o None si Redis no está disponible.
    None es el mecanismo de fallback: el repositorio lo maneja sin lanzar excepción.
    """
    global _pool
    global _next_retry_at

    with _pool_lock:
        if not settings.redis_cache_enabled:
            if _pool is not None:
                _pool.disconnect()
                _pool = None
            _next_retry_at = 0.0
            return None

        if _pool is None:
            now = time.monotonic()
            if now < _next_retry_at:
                return None

            _pool = _build_pool()
            if _pool is None:
                _next_retry_at = now + _retry_interval_seconds
                return None

            _next_retry_at = 0.0

        return Redis(connection_pool=_pool)
