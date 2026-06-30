from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.config import APP_NAME, APP_VERSION
from src.routers import compare, health
from src.services.sourceafis import SourceAfisEngine


@asynccontextmanager
async def lifespan(app: FastAPI):
    # JPype's embedded JVM cannot be cleanly restarted once shut down, so we
    # start it once here and let it go away with the process (no shutdown call).
    app.state.sourceafis = SourceAfisEngine()
    yield


app = FastAPI(title=APP_NAME, version=APP_VERSION, lifespan=lifespan)

app.include_router(health.router)
app.include_router(compare.router)
