from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from core.health import health_router
from db.session import create_db_and_tables, engine
from core.config import settings
from entrypoints.api.routers.internal import router as internal_router
from entrypoints.api.routers.hotel_reservations import router as hotel_router
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
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(router, prefix="/api/v1/reservations", tags=["reservations"])
app.include_router(hotel_router, prefix="/api/v1", tags=["hotel-reservations"])
app.include_router(internal_router, prefix="/api/v1", tags=["internal"])


@app.get("/health")
def health_check():
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="database unavailable") from exc
    return {"status": "ok"}
