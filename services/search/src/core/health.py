from fastapi import APIRouter, Response, status

from db.redis import get_redis_client

health_router = APIRouter(tags=["health"])


@health_router.get("/healthz/liveness")
def liveness():
    return {"status": "alive"}


@health_router.get("/healthz/readiness")
def readiness(response: Response):
    client = get_redis_client()
    if client is not None:
        try:
            client.ping()
            return {"status": "ready"}
        except Exception:
            pass
    response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {"status": "unavailable", "reason": "redis unreachable"}
