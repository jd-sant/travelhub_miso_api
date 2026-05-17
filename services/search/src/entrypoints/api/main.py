from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import settings
from core.health import health_router
from entrypoints.api.routers.search import router as search_router


def create_application() -> FastAPI:
    app = FastAPI(
        title="TravelHub - Search Service",
        version="2.0.0",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins,
        allow_credentials=settings.cors_allow_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health_router)
    app.include_router(search_router, prefix="/api/v1")

    @app.get("/health")
    def health_check() -> dict[str, str]:
        return {"status": "healthy"}

    return app


app = create_application()
