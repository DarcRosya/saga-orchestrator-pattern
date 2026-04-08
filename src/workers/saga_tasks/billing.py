import asyncio
import contextlib
import uuid
from typing import Any

import structlog
from sqlalchemy import select

from src.db.models.enums import OrderGlobalStatus, PaymentWay, SagaStepStatus
from src.db.models.order import Order
from src.workers.metrics import observe_step_duration, record_step_status

logger = structlog.get_logger(__name__)


async def process_billing(ctx: dict[str, Any], order_id: uuid.UUID) -> None:
    session_factory = ctx["session_factory"]
    http_client = ctx["http_client"]
    redis = ctx["redis"]

    log = logger.bind(order_id=str(order_id), task="process_billing")
    log.info("Starting billing processing")

    try:
        with observe_step_duration("billing"):
            async with session_factory() as session:
                stmt = select(Order).where(Order.id == order_id)
                result = await session.execute(stmt)
                order = result.scalars().first()

                if not order:
                    log.warning("Order not found")
                    return

                payment_type = order.payment_type

            billing_success = False
            billing_skip = False

            if payment_type == PaymentWay.POSTPAYMENT:
                log.info("Order is postpayment, skipping billing")
                billing_skip = True
                billing_status = SagaStepStatus.SKIPPED
            else:
                log.info("Sending billing request")
                billing_status = SagaStepStatus.FAILED
                try:
                    response = await http_client.post(f"http://mock-env:8080/billing/{order_id}")
                    if response.status_code == 200:
                        billing_success = True
                        billing_status = SagaStepStatus.SUCCESS
                    else:
                        log.warning(
                            "Billing failed with non-200 status", status_code=response.status_code
                        )
                except Exception:
                    log.error("Network or HTTP error during billing request", exc_info=True)

            record_step_status("billing", billing_status)

            async with session_factory() as session:
                stmt = select(Order).where(Order.id == order_id).with_for_update()
                result = await session.execute(stmt)
                order = result.scalars().first()

                if not order:
                    log.warning("Order not found during write phase")
                    return

                order.billing_status = billing_status

                if billing_skip or billing_success:
                    log.info("Billing successful or skipped, proceeding to next steps")
                    await asyncio.gather(
                        redis.enqueue_job(
                            "process_inventory",
                            order_id,
                            _job_id=f"inventory_{order_id}",
                            _queue_name="saga:tasks",
                        ),
                        redis.enqueue_job(
                            "process_logistic",
                            order_id,
                            _job_id=f"logistic_{order_id}",
                            _queue_name="saga:tasks",
                        ),
                    )
                else:
                    log.info("Billing failed, running compensation")
                    order.inventory_status = SagaStepStatus.CANCELLED
                    order.logistics_status = SagaStepStatus.CANCELLED
                    order.global_status = OrderGlobalStatus.COMPENSATING
                    await redis.enqueue_job(
                        "compensation",
                        order_id,
                        _job_id=f"compensation:{order_id}",
                        _queue_name="saga:tasks",
                    )

                await session.commit()
                log.info("Billing processing completed successfully")

    except Exception as e:
        log.error(
            "Critical infrastructural error in process_billing (DB or Redis failure)", exc_info=True
        )
        with contextlib.suppress(Exception):
            await redis.enqueue_job(
                "compensation",
                order_id,
                _job_id=f"compensation:{order_id}",
                _queue_name="saga:tasks",
            )
        raise e
