import asyncio
import uuid
from collections.abc import Coroutine
from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy import select

from src.db.models.enums import OrderGlobalStatus, SagaStepStatus
from src.db.models.order import Order
from src.services.notifications import send_critical_alert
from src.workers.metrics import (
    SAGA_STATUS,
    observe_step_duration,
    record_final_status_transition,
    record_step_status,
)

logger = structlog.get_logger("saga.compensation")


async def compensation(ctx: dict[str, Any], order_id: uuid.UUID, retry_count: int = 0) -> None:
    session_factory = ctx["session_factory"]
    http_client = ctx["http_client"]
    redis = ctx["redis"]

    logger.info("compensation.started", order_id=str(order_id))
    SAGA_STATUS.labels(status="compensation_attempted").inc()
    with observe_step_duration("compensation"):
        async with session_factory() as session:
            stmt = select(Order).where(Order.id == order_id).with_for_update()
            result = await session.execute(stmt)
            order = result.scalars().first()

            if not order:
                logger.error("compensation.order_not_found", order_id=str(order_id))
                return

            if (
                order.billing_status == SagaStepStatus.PENDING
                or order.inventory_status == SagaStepStatus.PENDING
                or order.logistics_status == SagaStepStatus.PENDING
            ):
                await session.rollback()
                logger.info("compensation.tasks_pending.defer", order_id=str(order_id))
                return

            billing_refund = order.billing_status == SagaStepStatus.SUCCESS
            inventory_release = order.inventory_status == SagaStepStatus.SUCCESS
            logistics_cancel = order.logistics_status == SagaStepStatus.SUCCESS

            order.global_status = OrderGlobalStatus.COMPENSATING
            order.updated_at = datetime.now(UTC).replace(tzinfo=None)
            await session.commit()

        tasks: list[Coroutine[Any, Any, tuple[str, bool]]] = []

        async def invoke_refund(service: str, url: str) -> tuple[str, bool]:
            try:
                resp = await http_client.post(url)
                success = resp.status_code == 200
                if not success:
                    logger.warning(
                        f"compensation.{service}_failed",
                        status=resp.status_code,
                        order_id=str(order_id),
                    )
                return service, success
            except Exception:
                logger.exception(f"compensation.{service}_exception", order_id=str(order_id))
                return service, False

        if billing_refund:
            tasks.append(
                invoke_refund("billing", f"http://mock-env:8080/billing/{order_id}/refund")
            )
        if inventory_release:
            tasks.append(
                invoke_refund("inventory", f"http://mock-env:8080/inventory/{order_id}/release")
            )
        if logistics_cancel:
            tasks.append(
                invoke_refund("logistics", f"http://mock-env:8080/logistics/{order_id}/cancel")
            )

        results: dict[str, bool] = {}
        if tasks:
            completed: list[tuple[str, bool]] = await asyncio.gather(*tasks)  # type: ignore
            results = dict(completed)

        async with session_factory() as session:
            stmt = select(Order).where(Order.id == order_id).with_for_update()
            result = await session.execute(stmt)
            order = result.scalars().first()

            if not order:
                logger.error("compensation.order_not_found_after_refund", order_id=str(order_id))
                return

            if billing_refund and results.get("billing"):
                order.billing_status = SagaStepStatus.COMPENSATED
            if inventory_release and results.get("inventory"):
                order.inventory_status = SagaStepStatus.COMPENSATED
            if logistics_cancel and results.get("logistics"):
                order.logistics_status = SagaStepStatus.COMPENSATED

            statuses = [order.billing_status, order.inventory_status, order.logistics_status]

            if SagaStepStatus.SUCCESS not in statuses:
                previous_status = order.global_status
                order.global_status = OrderGlobalStatus.CANCELLED
                record_final_status_transition(previous_status, order.global_status)
                record_step_status("compensation", SagaStepStatus.COMPENSATED)
                logger.info("compensation.finished.success", order_id=str(order_id))
                await session.commit()
            else:
                if retry_count >= 4:
                    logger.error("compensation.exhausted_retries", order_id=str(order_id))
                    order.global_status = OrderGlobalStatus.MANUAL_INTERVENTION_REQUIRED
                    SAGA_STATUS.labels(status="stuck").inc()
                    record_step_status("compensation", SagaStepStatus.FAILED)

                    await send_critical_alert(
                        order_id=str(order_id),
                        reason="Order stuck in COMPENSATING. Manual refund required.",
                        context={
                            "billing_status": order.billing_status.value,
                            "inventory_status": order.inventory_status.value,
                            "logistics_status": order.logistics_status.value,
                        },
                    )
                    await session.commit()
                else:
                    next_retry = retry_count + 1
                    record_step_status("compensation", SagaStepStatus.FAILED)
                    logger.warning(
                        "compensation.finished.partial.defer",
                        order_id=str(order_id),
                        retry_count=next_retry,
                    )
                    await session.commit()
                    await redis.enqueue_job(
                        "compensation",
                        order_id,
                        next_retry,
                        _job_id=f"compensation:{order_id}:{int(datetime.now(UTC).timestamp())}",
                        _queue_name="saga:tasks",
                        _defer_by=15,
                    )
