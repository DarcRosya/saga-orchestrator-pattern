from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.enums import OrderGlobalStatus, SagaStepStatus
from src.db.models.order import Order
from src.db.repositories.order import OrderRepository


@pytest.mark.asyncio
async def test_get_stuck_orders_for_compensation(
    db_session: AsyncSession,
    create_setup_order,
):
    # Arrange
    repo = OrderRepository(db_session)

    # 1. Stuck in PROCESSING for > 60 seconds (should be returned)
    order_stuck_proc, _ = await create_setup_order(global_status=OrderGlobalStatus.PROCESSING)
    past_time = datetime.now(UTC).replace(tzinfo=None) - timedelta(seconds=70)
    await db_session.execute(
        update(Order).where(Order.id == order_stuck_proc.id).values(updated_at=past_time)
    )

    # 2. In PROCESSING but recently created < 60 sec (should NOT be returned)
    order_recent_proc, _ = await create_setup_order(global_status=OrderGlobalStatus.PROCESSING)
    recent_time = datetime.now(UTC).replace(tzinfo=None) - timedelta(seconds=10)
    await db_session.execute(
        update(Order).where(Order.id == order_recent_proc.id).values(updated_at=recent_time)
    )

    # 3. Stuck in COMPENSATING with some SUCCESS statuses > 60 seconds (should be returned)
    order_stuck_comp, _ = await create_setup_order(global_status=OrderGlobalStatus.COMPENSATING)
    # Give it one SUCCESS so it matches the OR condition
    await db_session.execute(
        update(Order)
        .where(Order.id == order_stuck_comp.id)
        .values(billing_status=SagaStepStatus.SUCCESS, updated_at=past_time)
    )

    # 4. Completed order (should NOT be returned regardless of time)
    order_completed, _ = await create_setup_order(global_status=OrderGlobalStatus.COMPLETED)
    await db_session.execute(
        update(Order)
        .where(Order.id == order_completed.id)
        .values(
            billing_status=SagaStepStatus.SUCCESS,
            inventory_status=SagaStepStatus.SUCCESS,
            logistics_status=SagaStepStatus.SUCCESS,
            updated_at=past_time,
        )
    )

    await db_session.commit()

    # Act
    stuck_orders = await repo.get_stuck_orders_for_compensation(timeout_seconds=60)

    # Assert
    stuck_order_ids = {o.id for o in stuck_orders}

    assert len(stuck_orders) == 2
    assert order_stuck_proc.id in stuck_order_ids
    assert order_stuck_comp.id in stuck_order_ids

    assert order_recent_proc.id not in stuck_order_ids
    assert order_completed.id not in stuck_order_ids
