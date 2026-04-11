from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.auth_middleware import AuthMiddleware
from db.session import create_db_and_tables
from entrypoints.api.routers.auth import router as auth_router


@asynccontextmanager
async def lifespan(_: FastAPI):
    create_db_and_tables()
    yield


def create_application() -> FastAPI:
    app = FastAPI(title="TravelHub - Security Service", lifespan=lifespan)
    app.add_middleware(AuthMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )
    app.include_router(auth_router, prefix="/api/v1")

    @app.get("/health")
    def health_check() -> dict[str, str]:
        return {"status": "healthy"}

    return app


app = create_application()
