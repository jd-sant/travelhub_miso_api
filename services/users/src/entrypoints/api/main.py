from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.auth_middleware import AuthMiddleware
from core.config import settings
from core.health import health_router
from db.seed import seed_demo_hotels_if_empty
from db.session import create_db_and_tables, engine
from entrypoints.api.routers.internal import router as internal_router
from entrypoints.api.routers.users import router as users_router


@asynccontextmanager
async def lifespan(_: FastAPI):
    create_db_and_tables()
    if settings.demo_seed_enabled:
        from sqlmodel import Session

        with Session(engine) as session:
            seed_demo_hotels_if_empty(session)
    yield


def create_application() -> FastAPI:
    app = FastAPI(title="TravelHub - Users Service", lifespan=lifespan)
    app.add_middleware(AuthMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )
    app.include_router(health_router)
    app.include_router(users_router, prefix="/api/v1")
    app.include_router(internal_router, prefix="/api/v1")

    @app.get("/health")
    def health_check() -> dict[str, str]:
        return {"status": "healthy"}

    return app


app = create_application()
