from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.enums import OrderGlobalStatus
from src.db.models.order import Order
from src.workers.scheduler import poll_and_dispatch_orders


@pytest.mark.asyncio
async def test_scheduler_enqueues_stuck_orders(
    db_session: AsyncSession,
    create_setup_order,
):
    # Arrange
    # Insert a stuck order
    stuck_order, _ = await create_setup_order(global_status=OrderGlobalStatus.PROCESSING)
    past_time = datetime.now(UTC).replace(tzinfo=None) - timedelta(seconds=70)

    await db_session.execute(
        update(Order).where(Order.id == stuck_order.id).values(updated_at=past_time)
    )
    await db_session.commit()

    # Refresh to ensure we get DB date later
    await db_session.refresh(stuck_order)
    original_updated_at = stuck_order.updated_at

    mock_redis = AsyncMock()

    @asynccontextmanager
    async def mock_session_factory():
        from tests.conftest import TestingSessionLocal

        session = TestingSessionLocal()
        try:
            yield session
        finally:
            await session.close()

    ctx = {
        "session_factory": mock_session_factory,
        "redis": mock_redis,
    }

    # Act
    await poll_and_dispatch_orders(ctx)

    # Assert
    # Verify Redis enqueue was called for compensation
    mock_redis.enqueue_job.assert_called_once_with(
        "compensation",
        stuck_order.id,
        _job_id=f"compensation:{stuck_order.id}",
    )

    # Verify the stuck order's updated_at timestamp got modified to prevent rapid looping
    await db_session.refresh(stuck_order)
    assert stuck_order.updated_at > original_updated_at
