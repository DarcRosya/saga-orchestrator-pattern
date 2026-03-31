import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Good, Order


@pytest.mark.asyncio
async def test_create_order_success(
    api_client: AsyncClient,
    db_session: AsyncSession,
    mock_redis,
):
    # Arrange
    good = Good(name="Laptop", price=1500.0)
    db_session.add(good)
    await db_session.commit()

    idempotency_key = str(uuid.uuid4())
    payload = {
        "good_id": good.id,
        "idempotency_key": idempotency_key,
        "payment_type": "prepayment",
        "quantity": 2,
        "order_details": {
            "guest_email": "test@example.com",
            "guest_phone": "+1234567890",
            "region": "NY",
            "city": "New York",
            "delivery_service": "FedEx",
            "postal_address": "123 Main St",
        },
    }

    # Act
    response = await api_client.post("/order/", json=payload)
    print("RESPONSE", response.json())

    # Assert
    assert response.status_code == 201

    data = response.json()
    assert "id" in data
    assert data["global_status"] == "PROCESSING"

    # Verify DB
    order_id = data["id"]
    order = await db_session.get(Order, order_id)
    assert order is not None
    assert order.good_id == good.id
    assert order.idempotency_key == idempotency_key
    assert order.quantity == 2

    # Verify Redis enqueue
    mock_redis.enqueue_job.assert_called_once_with(
        "process_billing",
        str(order.id),
        _job_id=f"billing_{order.id}",
        _queue_name="saga:tasks",
    )


@pytest.mark.asyncio
async def test_create_order_idempotency_returns_existing(
    api_client: AsyncClient, db_session: AsyncSession, mock_redis, create_setup_order
):
    # Arrange
    order, good = await create_setup_order()

    # Use the same idempotency key to test idempotency
    payload = {
        "good_id": good.id,
        "idempotency_key": order.idempotency_key,
        "payment_type": "prepayment",
        "quantity": 1,
        "order_details": {
            "guest_email": "test@example.com",
            "guest_phone": "+1234567890",
            "region": "NY",
            "city": "New York",
            "delivery_service": "FedEx",
            "postal_address": "123 Main St",
        },
    }

    # Act
    response = await api_client.post("/order/", json=payload)

    # Assert
    assert response.status_code == 200  # Based on design, it should return 200 OK
    data = response.json()
    assert data["id"] == str(order.id)
    assert data["global_status"] == order.global_status.value

    # Redis should NOT be enqueued again
    mock_redis.enqueue_job.assert_not_called()


@pytest.mark.asyncio
async def test_create_order_good_not_found(api_client: AsyncClient, mock_redis):
    # Arrange
    payload = {
        "good_id": 9999,  # Non-existent
        "idempotency_key": str(uuid.uuid4()),
        "payment_type": "prepayment",
        "quantity": 1,
        "order_details": {
            "guest_email": "test@example.com",
            "guest_phone": "+1234567890",
            "region": "NY",
            "city": "New York",
            "delivery_service": "FedEx",
            "postal_address": "123 Main St",
        },
    }

    # Act
    response = await api_client.post("/order/", json=payload)

    # Assert
    assert response.status_code == 404
    assert "Goods not found" in response.json()["detail"]

    mock_redis.enqueue_job.assert_not_called()


@pytest.mark.asyncio
async def test_create_order_validation_error(api_client: AsyncClient, mock_redis):
    # Arrange
    payload = {
        "good_id": 1,
        "idempotency_key": str(uuid.uuid4()),
        "payment_type": "prepayment",
        "quantity": 0,  # Invalid quantity (must be >= 1)
        "order_details": {
            "guest_email": "invalid-email",  # Invalid email
            "guest_phone": "+1234567890",
            "region": "NY",
            "city": "New York",
            "delivery_service": "FedEx",
            "postal_address": "123 Main St",
        },
    }

    # Act
    response = await api_client.post("/order/", json=payload)

    # Assert
    assert response.status_code == 422
    errors = response.json()["detail"]
    assert any("quantity" in error["loc"] for error in errors)
    assert any("guest_email" in error["loc"] for error in errors)

    mock_redis.enqueue_job.assert_not_called()


@pytest.mark.asyncio
async def test_create_order_invalid_jwt(
    api_client: AsyncClient,
    db_session: AsyncSession,
    mock_redis,
):
    # Arrange
    good = Good(name="Monitor", price=300.0)
    db_session.add(good)
    await db_session.commit()

    payload = {
        "good_id": good.id,
        "idempotency_key": str(uuid.uuid4()),
        "payment_type": "prepayment",
        "quantity": 1,
        "order_details": {
            "guest_email": "test@example.com",
            "guest_phone": "+1234567890",
            "region": "NY",
            "city": "New York",
            "delivery_service": "FedEx",
            "postal_address": "123 Main St",
        },
    }

    # Act
    # Adding an invalid authorization token
    response = await api_client.post(
        "/order/", json=payload, headers={"Authorization": "Bearer invalid_token_here"}
    )

    # Assert
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid or expired token."

    mock_redis.enqueue_job.assert_not_called()


@pytest.mark.asyncio
async def test_create_order_bulk_success(
    api_client: AsyncClient,
    db_session: AsyncSession,
    mock_redis,
):
    # Arrange
    good1 = Good(name="Laptop", price=1500.0)
    good2 = Good(name="Mouse", price=300.0)
    db_session.add_all([good1, good2])
    await db_session.commit()

    payload = [
        {
            "good_id": good1.id,
            "idempotency_key": str(uuid.uuid4()),
            "payment_type": "prepayment",
            "quantity": 2,
            "order_details": {
                "guest_email": "test@example.com",
                "guest_phone": "+123",
                "region": "NY",
                "city": "NY",
                "delivery_service": "FedEx",
                "postal_address": "123 Main",
            },
        },
        {
            "good_id": good2.id,
            "idempotency_key": str(uuid.uuid4()),
            "payment_type": "postpayment",
            "quantity": 5,
            "order_details": {
                "guest_email": "test2@example.com",
                "guest_phone": "+124",
                "region": "CA",
                "city": "SF",
                "delivery_service": "UPS",
                "postal_address": "456 Side",
            },
        },
    ]

    # Act
    response = await api_client.post("/order/", json=payload)

    # Assert
    assert response.status_code == 201
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 2

    # Verify DB
    ids = [d["id"] for d in data]
    from sqlalchemy import select

    res = await db_session.execute(select(Order).where(Order.id.in_(ids)))
    orders = res.scalars().all()
    assert len(orders) == 2

    # Verify Redis enqueue
    assert mock_redis.enqueue_job.call_count == 2
