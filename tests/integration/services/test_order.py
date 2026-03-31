import uuid
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.enums import PaymentWay
from src.db.models.good import Good
from src.schemas.order import OrderCreate, OrderShippingDetailsCreate
from src.services.order import OrderService


@pytest.mark.asyncio
async def test_order_service_create(db_session: AsyncSession):
    # Arrange
    service = OrderService(db_session)
    mock_redis = AsyncMock()

    good = Good(name="Service Item", price=100.0)
    db_session.add(good)
    await db_session.commit()

    order_data = OrderCreate(
        good_id=good.id,
        idempotency_key=uuid.uuid4(),
        payment_type=PaymentWay.PREPAYMENT,
        quantity=1,
        order_details=OrderShippingDetailsCreate(
            guest_email="test@test.com",
            guest_phone="+12345",
            region="Reg",
            city="Cit",
            delivery_service="DHL",
            postal_address="123",
        ),
    )

    # Act
    order = await service.create(mock_redis, order_data, optional_user=None)

    # Assert
    assert order is not None
    assert order.good_id == good.id
    assert order.idempotency_key == str(order_data.idempotency_key)

    mock_redis.enqueue_job.assert_called_once_with(
        "process_billing",
        str(order.id),
        _job_id=f"billing_{order.id}",
        _queue_name="saga:tasks",
    )
async def test_order_service_create_invalid_good(db_session: AsyncSession):
    service = OrderService(db_session)
    mock_redis = AsyncMock()

    order_data = OrderCreate(
        good_id=99999,
        idempotency_key=uuid.uuid4(),
        payment_type=PaymentWay.PREPAYMENT,
        quantity=1,
        order_details=OrderShippingDetailsCreate(
            guest_email="test@test.com",
            guest_phone="+12345",
            region="Reg",
            city="Cit",
            delivery_service="DHL",
            postal_address="123",
        ),
    )

    with pytest.raises(HTTPException) as exc:
        await service.create(mock_redis, order_data, optional_user=None)

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_order_service_bulk_create(db_session: AsyncSession):
    # Arrange
    service = OrderService(db_session)
    mock_redis = AsyncMock()

    good1 = Good(name="Service Item 1", price=100.0)
    good2 = Good(name="Service Item 2", price=200.0)
    db_session.add_all([good1, good2])
    await db_session.commit()

    order_data_list = [
        OrderCreate(
            good_id=good1.id,
            idempotency_key=uuid.uuid4(),
            payment_type=PaymentWay.PREPAYMENT,
            quantity=1,
            order_details=OrderShippingDetailsCreate(
                guest_email="test@test.com",
                guest_phone="+12345",
                region="Reg",
                city="Cit",
                delivery_service="DHL",
                postal_address="123",
            ),
        ),
        OrderCreate(
            good_id=good2.id,
            idempotency_key=uuid.uuid4(),
            payment_type=PaymentWay.PREPAYMENT,
            quantity=2,
            order_details=OrderShippingDetailsCreate(
                guest_email="test2@test.com",
                guest_phone="+123456",
                region="Reg2",
                city="Cit2",
                delivery_service="UPS",
                postal_address="1234",
            ),
        ),
    ]

    # Act
    orders = await service.create_bulk(mock_redis, order_data_list, optional_user=None)

    # Assert
    assert len(orders) == 2
    assert orders[0].good_id == good1.id
    assert orders[1].good_id == good2.id

    assert mock_redis.enqueue_job.call_count == 2
