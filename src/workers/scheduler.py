from datetime import UTC, datetime
from typing import Any

from arq import cron

from core.settings import settings
from db.repositories.order import OrderRepository
from workers.lifecycle import shutdown, startup

DEFAULT_STUCK_TIMEOUT_SECONDS = 60


async def poll_and_dispatch_orders(ctx: dict[str, Any]) -> None:
    session_factory = ctx["session_factory"]
    redis = ctx["redis"]

    # log.info("scheduler.poll.started")

    try:
        async with session_factory() as session:
            repo = OrderRepository(session)

            # ── Stuck orders (compensation) ───────────────────────────────────
            try:
                stuck_orders = await repo.get_stuck_orders_for_compensation(
                    timeout_seconds=DEFAULT_STUCK_TIMEOUT_SECONDS
                )
            except Exception:
                # log.exception("scheduler.stuck_orders.fetch_failed")
                stuck_orders = []

            for order in stuck_orders:
                try:
                    await redis.enqueue_job(
                        "compensation",
                        order.id,
                        _job_id=f"compensation:{order.id}",
                    )
                    order.updated_at = datetime.now(UTC)
                    # log.info(
                    #     "scheduler.order.compensation_enqueued",
                    #     order_id=str(order.id), job=action.task_name,
                    #     next_status=action.next_status,
                    # )
                except Exception:
                    # log.exception(
                    #     "scheduler.order.compensation_failed",
                    #     order_id=str(order.id), job=action.task_name,
                    # )
                    pass

            await session.commit()
            # log.info(
            #     "scheduler.poll.finished",
            #     pending=len(pending_orders), stuck=len(stuck_orders),
            # )

    except Exception:
        # log.exception("scheduler.poll.unhandled_error")
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
