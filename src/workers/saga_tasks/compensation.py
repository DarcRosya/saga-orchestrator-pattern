import asyncio
import uuid
from collections.abc import Coroutine
from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy import select

from src.db.models.enums import OrderGlobalStatus, SagaStepStatus
from src.db.models.order import Order

logger = structlog.get_logger("saga.compensation")


async def compensation(ctx: dict[str, Any], order_id: uuid.UUID) -> None:
    session_factory = ctx["session_factory"]
    http_client = ctx["http_client"]

    logger.info("compensation.started", order_id=str(order_id))

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
            logger.warning("compensation.tasks_pending", order_id=str(order_id))
            raise Exception("Waiting for parallel tasks to finish")

        billing_refund = order.billing_status == SagaStepStatus.SUCCESS
        inventory_release = order.inventory_status == SagaStepStatus.SUCCESS
        logistics_cancel = order.logistics_status == SagaStepStatus.SUCCESS

        order.global_status = OrderGlobalStatus.COMPENSATING
        order.updated_at = datetime.now(UTC)
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
        tasks.append(invoke_refund("billing", f"http://mock_env/billing/{order_id}/refund"))
    if inventory_release:
        tasks.append(invoke_refund("inventory", f"http://mock_env/inventory/{order_id}/release"))
    if logistics_cancel:
        tasks.append(invoke_refund("logistics", f"http://mock_env/logistics/{order_id}/cancel"))

    results: dict[str, bool] = {}
    if tasks:
        completed: list[tuple[str, bool]] = await asyncio.gather(*tasks)  # type: ignore
        results = dict(completed)

    async with session_factory() as session:
        stmt = select(Order).where(Order.id == order_id).with_for_update()
        result = await session.execute(stmt)
        order = result.scalars().first()

        if billing_refund and results.get("billing"):
            order.billing_status = SagaStepStatus.COMPENSATED
        if inventory_release and results.get("inventory"):
            order.inventory_status = SagaStepStatus.COMPENSATED
        if logistics_cancel and results.get("logistics"):
            order.logistics_status = SagaStepStatus.COMPENSATED

        statuses = [order.billing_status, order.inventory_status, order.logistics_status]

        if SagaStepStatus.SUCCESS not in statuses:
            order.global_status = OrderGlobalStatus.CANCELLED
            logger.info("compensation.finished.success", order_id=str(order_id))
        else:
            logger.warning("compensation.finished.partial", order_id=str(order_id))

        await session.commit()
