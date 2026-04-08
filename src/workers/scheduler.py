import os
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog
from arq import cron
from prometheus_client import start_http_server
from sqlalchemy import func, select

from src.core.settings import settings
from src.db.models.enums import OrderGlobalStatus
from src.db.models.order import Order
from src.db.repositories.order import OrderRepository
from src.services.notifications import send_critical_alert
from src.workers.metrics import SAGA_MANUAL_STUCK_CURRENT, record_final_status_transition
from workers.lifecycle import shutdown
from workers.lifecycle import startup as base_startup

logger = structlog.get_logger("saga.scheduler")

DEFAULT_STUCK_TIMEOUT_SECONDS = 60


async def startup(ctx: dict[str, Any]) -> None:
    await base_startup(ctx)

    metrics_host = os.getenv("SAGA_SCHEDULER_METRICS_HOST", "0.0.0.0")
    metrics_port = int(os.getenv("SAGA_SCHEDULER_METRICS_PORT", "9102"))

    try:
        start_http_server(port=metrics_port, addr=metrics_host)
        logger.info("scheduler.metrics.endpoint_started", host=metrics_host, port=metrics_port)
    except OSError:
        logger.exception(
            "scheduler.metrics.endpoint_start_failed", host=metrics_host, port=metrics_port
        )


async def sync_manual_intervention_gauge(ctx: dict[str, Any]) -> None:
    session_factory = ctx["session_factory"]

    async with session_factory() as session:
        stmt = select(func.count(Order.id)).where(
            Order.global_status == OrderGlobalStatus.MANUAL_INTERVENTION_REQUIRED
        )
        result = await session.execute(stmt)
        manual_required_count = int(result.scalar() or 0)

    SAGA_MANUAL_STUCK_CURRENT.set(manual_required_count)
    logger.info("scheduler.metrics.manual_intervention_synced", count=manual_required_count)


async def check_and_alert_dead_orders(ctx: dict[str, Any]) -> None:
    session_factory = ctx["session_factory"]

    threshold = datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=1)

    async with session_factory() as session:
        stmt = select(Order).where(
            Order.global_status == OrderGlobalStatus.COMPENSATING, Order.updated_at < threshold
        )
        result = await session.execute(stmt)
        dead_orders = result.scalars().all()

        for order in dead_orders:
            await send_critical_alert(
                order_id=str(order.id),
                reason="Order stuck in COMPENSATING for over 1 hour. Manual refund required.",
                context={
                    "billing_status": order.billing_status.value,
                    "inventory_status": order.inventory_status.value,
                    "logistics_status": order.logistics_status.value,
                },
            )

            previous_status = order.global_status
            order.global_status = OrderGlobalStatus.MANUAL_INTERVENTION_REQUIRED
            record_final_status_transition(previous_status, order.global_status)

        if dead_orders:
            await session.commit()

    await sync_manual_intervention_gauge(ctx)
    logger.info("scheduler.dead_orders.processed", count=len(dead_orders))


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
                        _job_id=f"compensation:{order.id}:{int(datetime.now(UTC).timestamp())}",
                        _queue_name="saga:tasks",
                    )
                    order.updated_at = datetime.now(UTC).replace(tzinfo=None)
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
            await sync_manual_intervention_gauge(ctx)
            logger.info(
                "scheduler.poll.finished",
                stuck_orders_count=len(stuck_orders),
            )

    except Exception:
        logger.exception("scheduler.poll.unhandled_error")
        raise


class SchedulerWorkerSettings:
    redis_settings = settings.redis.arq_settings
    queue_name = "saga:scheduler"

    functions = [
        sync_manual_intervention_gauge,
        check_and_alert_dead_orders,
        poll_and_dispatch_orders,
    ]

    cron_jobs = [
        # every 30 seconds
        cron(
            poll_and_dispatch_orders,
            second={0, 30},
            unique=True,
        ),
        # every 10 minutes
        cron(
            check_and_alert_dead_orders,
            minute={0, 10, 20, 30, 40, 50},
            unique=True,
        ),
    ]

    on_startup = startup
    on_shutdown = shutdown

    max_jobs = 2
