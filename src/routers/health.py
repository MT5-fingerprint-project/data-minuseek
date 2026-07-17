from fastapi import APIRouter

from src.config import APP_NAME, APP_VERSION
from src.schemas import HealthResponse

router = APIRouter()


@router.get("/health")
def healthcheck() -> HealthResponse:
    return HealthResponse(status="ok", service=APP_NAME, version=APP_VERSION)
