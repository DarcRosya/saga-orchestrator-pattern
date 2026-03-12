from datetime import UTC, datetime
from typing import Any, NamedTuple

from arq import cron

from core.settings import settings
from db.models.enums import SagaStatus
from db.repositories.order import OrderRepository
from workers.lifecycle import shutdown, startup

DEFAULT_PENDING_TIMEOUT_SECONDS = 30
DEFAULT_STUCK_TIMEOUT_SECONDS = 60


class CompensationAction(NamedTuple):
    task_name: str
    next_status: SagaStatus


COMPENSATION_BY_STATUS: dict[SagaStatus, CompensationAction] = {
    SagaStatus.BILLING_STARTED: CompensationAction(
        "compensating_billing", SagaStatus.COMPENSATING_BILLING
    ),
    SagaStatus.BILLING_COMPLETED: CompensationAction(
        "compensating_billing", SagaStatus.COMPENSATING_BILLING
    ),
    SagaStatus.INVENTORY_STARTED: CompensationAction(
        "compensating_inventory", SagaStatus.COMPENSATING_INVENTORY
    ),
    SagaStatus.INVENTORY_COMPLETED: CompensationAction(
        "compensating_inventory", SagaStatus.COMPENSATING_INVENTORY
    ),
    SagaStatus.LOGISTICS_STARTED: CompensationAction(
        "compensating_logistics", SagaStatus.COMPENSATING_LOGISTICS
    ),
}


async def poll_and_dispatch_orders(ctx: dict[str, Any]) -> None:
    session_factory = ctx["session_factory"]
    redis = ctx["redis"]

    # log.info("scheduler.poll.started")

    try:
        async with session_factory() as session:
            repo = OrderRepository(session)

            # ── Pending orders ────────────────────────────────────────────────
            try:
                pending_orders = await repo.get_pending_orders(
                    timeout_seconds=DEFAULT_PENDING_TIMEOUT_SECONDS
                )
            except Exception:
                # log.exception("scheduler.pending_orders.fetch_failed")
                pending_orders = []

            for order in pending_orders:
                try:
                    await redis.enqueue_job(
                        "start_order_saga",
                        order.id,
                        _job_id=f"start_saga:{order.id}",
                    )
                    order.updated_at = datetime.now(UTC)
                    # log.info(
                    #     "scheduler.order.enqueued",
                    #     order_id=str(order.id), job="start_order_saga",
                    # )
                except Exception:
                    # log.exception(
                    #     "scheduler.order.enqueue_failed",
                    #     order_id=str(order.id), job="start_order_saga",
                    # )
                    pass

            # ── Stuck orders (compensation) ───────────────────────────────────
            try:
                stuck_orders = await repo.get_stuck_orders(
                    timeout_seconds=DEFAULT_STUCK_TIMEOUT_SECONDS
                )
            except Exception:
                # log.exception("scheduler.stuck_orders.fetch_failed")
                stuck_orders = []

            for order in stuck_orders:
                action = COMPENSATION_BY_STATUS.get(order.status)
                if not action:
                    continue
                try:
                    await redis.enqueue_job(
                        action.task_name,
                        order.id,
                        _job_id=f"compensation:{order.id}",
                    )
                    order.status = action.next_status
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
