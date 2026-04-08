import tomllib
from contextlib import asynccontextmanager
from pathlib import Path

from arq import create_pool
from arq.connections import RedisSettings
from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator
from prometheus_fastapi_instrumentator.metrics import default as default_metrics

from src.api.endpoints import include_routers  # type: ignore
from src.api.middleware import LoggingMiddleware
from src.core.logging import setup_logging
from src.core.seed import seed_goods
from src.core.settings import settings

setup_logging()


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
    app.state.redis_pool = await create_pool(
        RedisSettings(
            host=settings.redis.R_HOST,
            port=settings.redis.R_PORT,
        )
    )

    await seed_goods()

    yield  # App is running

    await app.state.redis_pool.close()


app = FastAPI(
    title="Saga Orchestrator",
    version=get_version(),
    description="""
    Distributed Transaction Management Core (Saga Pattern).
    The orchestrator accepts requests to create orders, manages the state machine,
    and guarantees eventual consistency during network failures in external services
    (billing, inventory, logistics) by executing transactions or automatic compensations.
    """,
    debug=settings.DEBUG_MODE,
    lifespan=lifespan,
    root_path="/api",
)

app.add_middleware(LoggingMiddleware)
instrumentator = Instrumentator()
instrumentator.add(
    default_metrics(
        latency_lowr_buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0),
    )
)
instrumentator.instrument(app).expose(app)


@app.get("/health", tags=["System"])
async def health_check():
    return {"status": "ok", "service": "saga-api", "version": app.version}


include_routers(app)
