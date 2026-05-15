from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from core.config import settings
from db.session import create_db_and_tables, engine
from entrypoints.api.routers.internal import router as internal_router
from entrypoints.api.routers.payments import router as payments_router


@asynccontextmanager
async def lifespan(_: FastAPI):
    if not settings.skip_db_init_on_startup:
        create_db_and_tables()
    yield


def create_application() -> FastAPI:
    app = FastAPI(title="TravelHub - Payments Service", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_cors_origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(payments_router, prefix="/api/v1")
    app.include_router(internal_router, prefix="/api/v1")

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
