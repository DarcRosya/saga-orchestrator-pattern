from uuid import uuid4

import pytest
from pydantic import ValidationError

from src.db.models.enums import PaymentWay
from src.schemas.order import OrderCreate


def test_order_create_valid():
    payload = {
        "good_id": 1,
        "idempotency_key": str(uuid4()),
        "payment_type": "prepayment",
        "quantity": 5,
        "order_details": {
            "guest_email": "test@test.com",
            "guest_phone": "+123456",
            "region": "Region",
            "city": "City",
            "delivery_service": "DHL",
            "postal_address": "123 Street",
        },
    }

    order = OrderCreate(**payload)
    assert order.good_id == 1
    assert order.quantity == 5
    assert order.payment_type == PaymentWay.PREPAYMENT
    assert order.order_details.guest_email == "test@test.com"


def test_order_create_invalid_quantity():
    payload = {
        "good_id": 1,
        "idempotency_key": str(uuid4()),
        "payment_type": "prepayment",
        "quantity": 0,  # Invalid: ge=1 expected
        "order_details": {
            "guest_email": "test@test.com",
            "guest_phone": "+123456",
            "region": "Region",
            "city": "City",
            "delivery_service": "DHL",
            "postal_address": "123 Street",
        },
    }

    with pytest.raises(ValidationError) as exc:
        OrderCreate(**payload)

    assert "quantity" in str(exc.value)


def test_order_create_invalid_email():
    payload = {
        "good_id": 1,
        "idempotency_key": str(uuid4()),
        "payment_type": "prepayment",
        "quantity": 1,
        "order_details": {
            "guest_email": "not-an-email",
            "guest_phone": "+123456",
            "region": "Region",
            "city": "City",
            "delivery_service": "DHL",
            "postal_address": "123 Street",
        },
    }

    with pytest.raises(ValidationError) as exc:
        OrderCreate(**payload)

    assert "guest_email" in str(exc.value)
