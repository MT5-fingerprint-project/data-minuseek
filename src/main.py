from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.comparison.adapters.inbound.http import router as comparison_router

APP_NAME = "data-dacty"
APP_VERSION = "0.1.0"

app = FastAPI(title=APP_NAME, version=APP_VERSION)

# POC / vertical slice : CORS permissif pour autoriser l'appel depuis le front.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(comparison_router)


@app.get("/health")
def healthcheck() -> dict[str, str]:
    return {
        "status": "ok",
        "service": APP_NAME,
        "version": APP_VERSION,
    }
