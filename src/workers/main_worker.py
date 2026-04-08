import os
from typing import Any

import structlog
from prometheus_client import start_http_server

from src.core.settings import settings
from workers.lifecycle import shutdown
from workers.lifecycle import startup as base_startup
from workers.saga_tasks.billing import process_billing
from workers.saga_tasks.compensation import compensation
from workers.saga_tasks.inventory import process_inventory
from workers.saga_tasks.logistics import process_logistic

logger = structlog.get_logger("saga.worker")


async def startup(ctx: dict[str, Any]) -> None:
    await base_startup(ctx)

    metrics_host = os.getenv("SAGA_WORKER_METRICS_HOST", "0.0.0.0")
    metrics_port = int(os.getenv("SAGA_WORKER_METRICS_PORT", "9101"))

    try:
        start_http_server(port=metrics_port, addr=metrics_host)
        logger.info("worker.metrics.started", host=metrics_host, port=metrics_port)
    except OSError:
        logger.exception("worker.metrics.start_failed", host=metrics_host, port=metrics_port)


class SagaWorkerSettings:
    redis_settings = settings.redis.arq_settings
    queue_name = "saga:tasks"

    functions = [compensation, process_billing, process_inventory, process_logistic]  # pyright: ignore[reportUnknownVariableType]

    on_startup = startup
    on_shutdown = shutdown

    max_jobs = 15
    job_timeout = 60
