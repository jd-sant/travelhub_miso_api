from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Traveler-Id", "X-Internal-Api-Key"],
)

app.include_router(router, prefix="/api/v1/reservations", tags=["reservations"])
app.include_router(internal_router, prefix="/api/v1", tags=["internal"])


@app.get("/health")
def health_check():
    return {"status": "ok"}
