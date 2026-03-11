import tomllib
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from core.settings import settings


def get_version() -> str:
    pyproject_path = Path(__file__).resolve().parent.parent / "pyproject.toml"
    try:
        with open(pyproject_path, "rb") as f:
            data = tomllib.load(f)
            return data["tool"]["poetry"]["version"]
    except (FileNotFoundError, KeyError):
        return "0.0.0-unknown"


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield  # App is running


app = FastAPI(
    title="Saga Orchestrator",
    version=get_version(),
    description="""
    Distributed Transaction Management Core (Saga Pattern).
    The orchestrator accepts requests to create orders, manages the state machine,
    and guarantees eventual consistency during network failures in external services
    (billing, inventory, logistics) by executing transactions or automatic compensations.
    """,
    debug=settings.debug_mode,
    lifespan=lifespan,
    # servers=[{"url": "/api", "description": "Default"}],
)


@app.get("/health", tags=["System"])
async def health_check():
    return {"status": "ok", "service": "saga-api", "version": app.version}
