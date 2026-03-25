import asyncio
from contextlib import asynccontextmanager
from typing import Any, Callable, Coroutine  # noqa: UP035

import pytest
from httpx import AsyncClient
from pytest_httpx import HTTPXMock
from pytest_mock import MockerFixture
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Good, Order
from src.db.models.enums import OrderGlobalStatus, PaymentWay, SagaStepStatus
from src.services.order import OrderService
from src.workers.saga_tasks.billing import process_billing
from src.workers.saga_tasks.compensation import compensation
from src.workers.saga_tasks.inventory import process_inventory
from src.workers.saga_tasks.logistics import process_logistic


@pytest.mark.asyncio
async def test_saga_happy_path(
    db_session: AsyncSession,
    httpx_mock: HTTPXMock,
    mocker: MockerFixture,
    order_service: OrderService,
    create_setup_order: Callable[..., Coroutine[Any, Any, tuple[Order, Good]]],
):
    order, good = await create_setup_order()  # type: ignore
    order_id = order.id

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

        # Wait for potential async commits to finish inside workers
        await asyncio.sleep(0.1)

    db_session.expire_all()

    updated_order = await order_service.get(str(order_id))

    assert updated_order is not None
    assert updated_order.billing_status == SagaStepStatus.SUCCESS
    assert updated_order.inventory_status == SagaStepStatus.SUCCESS
    assert updated_order.logistics_status == SagaStepStatus.SUCCESS
    assert updated_order.global_status == OrderGlobalStatus.COMPLETED

    assert fake_redis.enqueue_job.called


async def test_saga_compensation(
    db_session: AsyncSession,
    httpx_mock: HTTPXMock,
    mocker: MockerFixture,
    order_service: OrderService,
    create_setup_order: Callable[..., Coroutine[Any, Any, tuple[Order, Good]]],
):
    order, good = await create_setup_order()  # type: ignore
    order_id = order.id

    httpx_mock.add_response(
        url=f"http://mock_env/billing/{order_id}", status_code=200, json={"status": "ok"}
    )
    httpx_mock.add_response(
        url=f"http://mock_env/inventory/{order_id}", status_code=200, json={"status": "ok"}
    )
    httpx_mock.add_response(
        url=f"http://mock_env/logistic/{order_id}", status_code=500, json={"error": "boom"}
    )

    httpx_mock.add_response(
        url=f"http://mock_env/billing/{order_id}/refund",
        status_code=200,
        json={"status": "refunded"},
    )
    httpx_mock.add_response(
        url=f"http://mock_env/inventory/{order_id}/release",
        status_code=200,
        json={"status": "released"},
    )

    fake_redis = mocker.AsyncMock()

    @asynccontextmanager
    async def fake_session_factory():
        from tests.conftest import TestingSessionLocal

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

        await compensation(ctx, order_id)

    db_session.expire_all()

    updated_order = await order_service.get(str(order_id))

    assert updated_order is not None
    assert updated_order.billing_status == SagaStepStatus.COMPENSATED
    assert updated_order.inventory_status == SagaStepStatus.COMPENSATED
    assert updated_order.logistics_status == SagaStepStatus.FAILED
    assert updated_order.global_status == OrderGlobalStatus.CANCELLED


async def test_saga_billing_failed(
    db_session: AsyncSession,
    httpx_mock: HTTPXMock,
    mocker: MockerFixture,
    order_service: OrderService,
    create_setup_order: Callable[..., Coroutine[Any, Any, tuple[Order, Good]]],
):
    order, good = await create_setup_order()  # type: ignore
    order_id = order.id

    # Billing fails
    httpx_mock.add_response(
        url=f"http://mock_env/billing/{order_id}",
        status_code=500,
        json={"error": "insufficient funds"},
    )

    fake_redis = mocker.AsyncMock()

    @asynccontextmanager
    async def fake_session_factory():
        from tests.conftest import TestingSessionLocal

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

        # Run billing
        await process_billing(ctx, order_id)

        # When billing fails, compensation is called right away. Inventory and logistics are not even started.
        await compensation(ctx, order_id)

    db_session.expire_all()
    updated_order = await order_service.get(str(order_id))

    assert updated_order is not None
    assert updated_order.billing_status == SagaStepStatus.FAILED
    # None or pending based on defaults
    assert updated_order.global_status == OrderGlobalStatus.CANCELLED


async def test_saga_postpayment_path(
    db_session: AsyncSession,
    httpx_mock: HTTPXMock,
    mocker: MockerFixture,
    order_service: OrderService,
    create_setup_order: Callable[..., Coroutine[Any, Any, tuple[Order, Good]]],
):
    order, good = await create_setup_order()  # type: ignore
    order_id = order.id

    # modify to postpayment
    order.payment_type = PaymentWay.POSTPAYMENT
    db_session.add(order)
    await db_session.commit()

    # Only inventory and logistics need to be mocked
    httpx_mock.add_response(
        url=f"http://mock_env/inventory/{order_id}", status_code=200, json={"status": "success"}
    )
    httpx_mock.add_response(
        url=f"http://mock_env/logistic/{order_id}", status_code=200, json={"status": "success"}
    )

    fake_redis = mocker.AsyncMock()

    @asynccontextmanager
    async def fake_session_factory():
        from tests.conftest import TestingSessionLocal

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

        # Wait for potential async commits to finish inside workers
        await asyncio.sleep(0.1)

    db_session.expire_all()
    updated_order = await order_service.get(str(order_id))

    assert updated_order is not None
    assert updated_order.billing_status == SagaStepStatus.SKIPPED
    assert updated_order.inventory_status == SagaStepStatus.SUCCESS
    assert updated_order.logistics_status == SagaStepStatus.SUCCESS
    assert updated_order.global_status == OrderGlobalStatus.COMPLETED
