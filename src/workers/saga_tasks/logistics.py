import contextlib
import uuid
from typing import Any

import structlog
from sqlalchemy import select

from db.models.enums import OrderGlobalStatus, SagaStepStatus
from db.models.order import Order

logger = structlog.get_logger(__name__)


async def process_logistic(ctx: dict[str, Any], order_id: uuid.UUID) -> None:
    session_factory = ctx["session_factory"]
    http_client = ctx["http_client"]
    redis = ctx["redis"]

    log = logger.bind(order_id=str(order_id), task="process_logistic")
    log.info("Starting logistic processing")

    try:
        log.info("Sending logistic check request")
        logistics_status = SagaStepStatus.FAILED
        try:
            response = await http_client.post(f"http://mock_env/logistic/{order_id}")
            if response.status_code == 200:
                logistics_status = SagaStepStatus.SUCCESS
            else:
                log.warning("Logistic failed with non-200 status", status_code=response.status_code)
        except Exception:
            log.error("Network or HTTP error during logistic request", exc_info=True)

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
                order.logistics_status = logistics_status
                await session.commit()
                return

            order.logistics_status = logistics_status

            if logistics_status == SagaStepStatus.SUCCESS:
                if order.inventory_status == SagaStepStatus.SUCCESS and order.billing_status in (
                    SagaStepStatus.SUCCESS,
                    SagaStepStatus.SKIPPED,
                ):
                    order.global_status = OrderGlobalStatus.COMPLETED
                    log.info("All saga steps completed. Order marked as COMPLETED.")
            else:
                log.info("Logistic check failed, triggering compensation")
                order.global_status = OrderGlobalStatus.COMPENSATING
                await redis.enqueue_job(
                    "compensation", order_id, _job_id=f"compensation:{order_id}"
                )

            await session.commit()
            log.info("Logistic processing finished successfully")

    except Exception as e:
        log.error("Critical infrastructural error in process_logistic", exc_info=True)
        with contextlib.suppress(Exception):
            await redis.enqueue_job("compensation", order_id, _job_id=f"compensation:{order_id}")
        raise e
