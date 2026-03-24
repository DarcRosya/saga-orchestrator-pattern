from datetime import UTC, datetime
from typing import Any

import structlog
from arq import cron

from src.core.settings import settings
from src.db.repositories.order import OrderRepository
from workers.lifecycle import shutdown, startup

logger = structlog.get_logger("saga.scheduler")

DEFAULT_STUCK_TIMEOUT_SECONDS = 60


async def poll_and_dispatch_orders(ctx: dict[str, Any]) -> None:
    session_factory = ctx["session_factory"]
    redis = ctx["redis"]

    logger.info("scheduler.poll.started")

    try:
        async with session_factory() as session:
            repo = OrderRepository(session)

            # ── Stuck orders (compensation) ───────────────────────────────────
            try:
                stuck_orders = await repo.get_stuck_orders_for_compensation(
                    timeout_seconds=DEFAULT_STUCK_TIMEOUT_SECONDS
                )
            except Exception:
                logger.exception("scheduler.stuck_orders.fetch_failed")
                stuck_orders = []

            for order in stuck_orders:
                try:
                    await redis.enqueue_job(
                        "compensation",
                        order.id,
                        _job_id=f"compensation:{order.id}",
                    )
                    order.updated_at = datetime.now(UTC)
                    logger.info(
                        "scheduler.order.compensation_enqueued",
                        order_id=str(order.id),
                        job="compensation",
                    )
                except Exception:
                    logger.exception(
                        "scheduler.order.compensation_failed",
                        order_id=str(order.id),
                        job="compensation",
                    )
                    pass

            await session.commit()
            logger.info(
                "scheduler.poll.finished",
                stuck_orders_count=len(stuck_orders),
            )

    except Exception:
        logger.exception("scheduler.poll.unhandled_error")
        raise


class SchedulerWorkerSettings:
    redis_settings = settings.redis.arq_settings

    functions = [poll_and_dispatch_orders]

    cron_jobs = [
        cron(
            poll_and_dispatch_orders,
            second={0, 10, 20, 30, 40, 50},  # every 10 seconds
            unique=True,
        )
    ]

    on_startup = startup
    on_shutdown = shutdown

    max_jobs = 15
    job_timeout = 15
