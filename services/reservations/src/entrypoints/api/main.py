from contextlib import asynccontextmanager

from fastapi import FastAPI

from db.session import create_db_and_tables
from entrypoints.api.routers.reservations import router

@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    yield


app = FastAPI(title="Reservations Service", version="1.0.0", lifespan=lifespan)


app.include_router(router, prefix="/api/v1/reservations", tags=["reservations"])


@app.get("/health")
def health_check():
    return {"status": "ok"}
