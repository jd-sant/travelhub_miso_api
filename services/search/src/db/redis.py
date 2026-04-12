import logging
from typing import Optional

from redis import Redis, ConnectionPool
from redis.exceptions import RedisError

from core.config import settings

logger = logging.getLogger(__name__)

_pool: Optional[ConnectionPool] = None


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


_pool = _build_pool()


def get_redis_client() -> Optional[Redis]:
    """
    Retorna cliente Redis listo para usar, o None si Redis no está disponible.
    None es el mecanismo de fallback: el repositorio lo maneja sin lanzar excepción.
    """
    if _pool is None:
        return None
    return Redis(connection_pool=_pool)
