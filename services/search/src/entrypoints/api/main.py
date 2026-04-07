from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from db.seed import seed_dummy_data_if_needed
from db.session import create_db_and_tables
from entrypoints.api.routers.search import router as search_router


@asynccontextmanager
async def lifespan(_: FastAPI):
    create_db_and_tables()
    seed_dummy_data_if_needed()
    yield


def create_application() -> FastAPI:
    app = FastAPI(title="TravelHub - Search Service", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(search_router, prefix="/api/v1")

    @app.get("/health")
    def health_check() -> dict[str, str]:
        return {"status": "healthy"}

    return app


app = create_application()