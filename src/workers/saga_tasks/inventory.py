import contextlib
import uuid
from typing import Any

import structlog
from sqlalchemy import select

from src.db.models.enums import OrderGlobalStatus, SagaStepStatus
from src.db.models.order import Order
from src.workers.metrics import (
    observe_step_duration,
    record_final_status_transition,
    record_step_status,
)

logger = structlog.get_logger(__name__)


async def process_inventory(ctx: dict[str, Any], order_id: uuid.UUID) -> None:
    session_factory = ctx["session_factory"]
    http_client = ctx["http_client"]
    redis = ctx["redis"]

    log = logger.bind(order_id=str(order_id), task="process_inventory")
    log.info("Starting inventory processing")

    try:
        with observe_step_duration("inventory"):
            log.info("Sending inventory check request")
            inventory_status = SagaStepStatus.FAILED
            try:
                response = await http_client.post(f"http://mock-env:8080/inventory/{order_id}")
                if response.status_code == 200:
                    inventory_status = SagaStepStatus.SUCCESS
                else:
                    log.warning(
                        "Inventory failed with non-200 status", status_code=response.status_code
                    )
            except Exception:
                log.error("Network or HTTP error during inventory request", exc_info=True)

            record_step_status("inventory", inventory_status)

            async with session_factory() as session:
                stmt = select(Order).where(Order.id == order_id).with_for_update()
                result = await session.execute(stmt)
                order = result.scalars().first()

                if not order:
                    log.warning("Order not found during write phase")
                    return

                if order.global_status == OrderGlobalStatus.COMPENSATING:
                    log.info(
                        "Saga was already started compensation by another worker. Just saving my status."  # noqa: E501
                    )
                    order.inventory_status = inventory_status
                    await session.commit()
                    return

                order.inventory_status = inventory_status

                if inventory_status == SagaStepStatus.SUCCESS:
                    if (
                        order.logistics_status == SagaStepStatus.SUCCESS
                        and order.billing_status
                        in (
                            SagaStepStatus.SUCCESS,
                            SagaStepStatus.SKIPPED,
                        )
                    ):
                        previous_status = order.global_status
                        order.global_status = OrderGlobalStatus.COMPLETED
                        record_final_status_transition(previous_status, order.global_status)
                        log.info("All saga steps completed. Order marked as COMPLETED.")
                else:
                    log.info("Inventory check failed, triggering compensation")
                    order.global_status = OrderGlobalStatus.COMPENSATING
                    await redis.enqueue_job(
                        "compensation",
                        order_id,
                        _job_id=f"compensation:{order_id}",
                        _queue_name="saga:tasks",
                    )

                await session.commit()
                log.info("Inventory processing finished successfully")

    except Exception as e:
        log.error("Critical infrastructural error in process_inventory", exc_info=True)
        with contextlib.suppress(Exception):
            await redis.enqueue_job(
                "compensation",
                order_id,
                _job_id=f"compensation:{order_id}",
                _queue_name="saga:tasks",
            )
        raise e
