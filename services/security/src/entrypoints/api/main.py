from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from core.auth_middleware import AuthMiddleware
from core.config import settings
from core.health import health_router
from db.session import create_db_and_tables, engine
from entrypoints.api.routers.auth import router as auth_router
from entrypoints.api.routers.privacy import router as privacy_router


@asynccontextmanager
async def lifespan(_: FastAPI):
    create_db_and_tables()
    yield


def create_application() -> FastAPI:
    app = FastAPI(title="TravelHub - Security Service", lifespan=lifespan)
    app.add_middleware(AuthMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )
    app.include_router(health_router)
    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(privacy_router, prefix="/api/v1")

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
