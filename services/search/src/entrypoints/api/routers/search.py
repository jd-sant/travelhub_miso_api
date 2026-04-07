from fastapi import APIRouter

router = APIRouter(prefix="/search", tags=["search"])


@router.get("/status")
def search_status() -> dict[str, str]:
    return {"service": "search", "status": "ok"}