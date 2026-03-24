import asyncio
import uuid
from contextlib import asynccontextmanager
from typing import Any

import pytest
from httpx import AsyncClient
from pytest_httpx import HTTPXMock
from pytest_mock import MockerFixture
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.enums import OrderGlobalStatus, PaymentWay, SagaStepStatus
from src.db.models.good import Good
from src.db.models.order import Order
from src.services.order import OrderService
from src.workers.saga_tasks.billing import process_billing
from src.workers.saga_tasks.inventory import process_inventory
from src.workers.saga_tasks.logistics import process_logistic


@pytest.mark.asyncio
async def test_saga_happy_path(
    db_session: AsyncSession,
    httpx_mock: HTTPXMock,
    mocker: MockerFixture,
    order_service: OrderService,
):
    good = Good(id=0, name="Coca-cola", price=10.99)
    order_id = uuid.uuid4()
    idempotency_key = str(uuid.uuid4())

    order = Order(
        id=order_id,
        good_id=good.id,
        idempotency_key=idempotency_key,
        billing_status=SagaStepStatus.PENDING,
        inventory_status=SagaStepStatus.PENDING,
        logistics_status=SagaStepStatus.PENDING,
        global_status=OrderGlobalStatus.PROCESSING,
        payment_type=PaymentWay.PREPAYMENT,
        quantity=1,
    )
    db_session.add(good)
    db_session.add(order)
    await db_session.commit()

    httpx_mock.add_response(status_code=200, json={"status": "success"})
    httpx_mock.add_response(status_code=200, json={"status": "success"})
    httpx_mock.add_response(status_code=200, json={"status": "success"})

    fake_redis = mocker.AsyncMock()

    @asynccontextmanager
    async def fake_session_factory():
        from tests.conftest import TestingSessionLocal

        # Use a new session for each worker to allow concurrent gather
        session = TestingSessionLocal()
        try:
            yield session
        finally:
            await session.close()

    async with AsyncClient() as http_client:
        ctx: dict[str, Any] = {
            "session_factory": fake_session_factory,
            "http_client": http_client,
            "redis": fake_redis,
        }

        await process_billing(ctx, order_id)

        await asyncio.gather(
            process_inventory(ctx, order_id),
            process_logistic(ctx, order_id),
        )

    db_session.expire_all()

    updated_order = await order_service.get(str(order_id))

    assert updated_order is not None
    assert updated_order.billing_status == SagaStepStatus.SUCCESS
    assert updated_order.inventory_status == SagaStepStatus.SUCCESS
    assert updated_order.logistics_status == SagaStepStatus.SUCCESS
    assert updated_order.global_status == OrderGlobalStatus.COMPLETED

    assert fake_redis.enqueue_job.called
