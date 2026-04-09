from contextlib import asynccontextmanager

from fastapi import FastAPI

from db.session import create_db_and_tables
from entrypoints.api.routers.properties import (
    router as properties_router,
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    create_db_and_tables()
    yield


def create_application() -> FastAPI:
    app = FastAPI(
        title="TravelHub - Properties Service",
        lifespan=lifespan
    )
    app.include_router(properties_router, prefix="/api/v1")

    @app.get("/health")
    def health_check() -> dict[str, str]:
        return {"status": "healthy"}

    return app


app = create_application()
