from contextlib import asynccontextmanager

from fastapi import FastAPI

from db.session import create_db_and_tables
from core.config import settings
from entrypoints.api.routers.internal import router as internal_router
from entrypoints.api.routers.reservations import router

@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    settings.validate_scheduler_config()
    yield


app = FastAPI(title="Reservations Service", version="1.0.0", lifespan=lifespan)


app.include_router(router, prefix="/api/v1/reservations", tags=["reservations"])
app.include_router(internal_router, prefix="/api/v1", tags=["internal"])


@app.get("/health")
def health_check():
    return {"status": "ok"}
