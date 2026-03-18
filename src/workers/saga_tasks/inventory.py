import contextlib
import uuid
from typing import Any

import structlog
from sqlalchemy import select

from db.models.enums import OrderGlobalStatus, SagaStepStatus
from db.models.order import Order

logger = structlog.get_logger(__name__)


async def process_inventory(ctx: dict[str, Any], order_id: uuid.UUID) -> None:
    session_factory = ctx["session_factory"]
    http_client = ctx["http_client"]
    redis = ctx["redis"]

    log = logger.bind(order_id=str(order_id), task="process_inventory")
    log.info("Starting inventory processing")

    try:
        log.info("Sending inventory check request")
        inventory_status = SagaStepStatus.FAILED
        try:
            response = await http_client.post(f"http://mock_env/inventory/{order_id}")
            if response.status_code == 200:
                inventory_status = SagaStepStatus.SUCCESS
            else:
                log.warning(
                    "Inventory failed with non-200 status", status_code=response.status_code
                )
        except Exception:
            log.error("Network or HTTP error during inventory request", exc_info=True)

        async with session_factory() as session:
            stmt = select(Order).where(Order.id == order_id).with_for_update()
            result = await session.execute(stmt)
            order = result.scalars().first()

            if not order:
                log.warning("Order not found during write phase")
                return

            if order.global_status == OrderGlobalStatus.CANCELLED:
                log.info("Saga was already cancelled by another worker. Just saving my status.")
                order.inventory_status = inventory_status
                await session.commit()
                return

            order.inventory_status = inventory_status

            if inventory_status == SagaStepStatus.SUCCESS:
                if order.logistics_status == SagaStepStatus.SUCCESS and order.billing_status in (
                    SagaStepStatus.SUCCESS,
                    SagaStepStatus.SKIPPED,
                ):
                    order.status = OrderGlobalStatus.COMPLETED
                    log.info("All saga steps completed. Order marked as COMPLETED.")
            else:
                log.info("Inventory check failed, triggering compensation")
                order.global_status = OrderGlobalStatus.CANCELLED
                await redis.enqueue_job(
                    "compensation", order_id, _job_id=f"compensation:{order_id}"
                )

            await session.commit()
            log.info("Inventory processing finished successfully")

    except Exception as e:
        log.error("Critical infrastructural error in process_inventory", exc_info=True)
        with contextlib.suppress(Exception):
            await redis.enqueue_job("compensation", order_id, _job_id=f"compensation:{order_id}")
        raise e
