from fastapi import APIRouter, Response, status
from sqlalchemy import text
from sqlmodel import Session

from db.session import engine

health_router = APIRouter(tags=["health"])


def _db_connectable() -> bool:
    try:
        with Session(engine) as session:
            session.exec(text("SELECT 1"))
        return True
    except Exception:
        return False


@health_router.get("/healthz/liveness")
def liveness():
    return {"status": "alive"}


@health_router.get("/healthz/readiness")
def readiness(response: Response):
    if _db_connectable():
        return {"status": "ready"}
    response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {"status": "unavailable", "reason": "database unreachable"}
