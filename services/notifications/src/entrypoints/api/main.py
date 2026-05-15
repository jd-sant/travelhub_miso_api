from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from core.config import settings
from db.session import create_db_and_tables, engine
from entrypoints.api.routers.internal_notifications import router as internal_router
from entrypoints.api.routers.me import router as me_router
from entrypoints.api.routers.notifications import router as notifications_router


@asynccontextmanager
async def lifespan(_: FastAPI):
    if not settings.skip_db_init_on_startup:
        create_db_and_tables()
    yield


def create_application() -> FastAPI:
    app = FastAPI(title="TravelHub - Notifications Service", lifespan=lifespan)
    app.include_router(internal_router, prefix="/api/v1")
    app.include_router(notifications_router, prefix="/api/v1")
    app.include_router(me_router, prefix="/api/v1")

    @app.get("/health")
    def health_check() -> dict[str, str]:
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
        except SQLAlchemyError as exc:
            raise HTTPException(status_code=503, detail="database unavailable") from exc
        return {"status": "healthy"}

    return app


app = create_application()
