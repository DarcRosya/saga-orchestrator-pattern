import uuid

from pydantic import BaseModel, EmailStr, Field

from src.db.models.enums import OrderGlobalStatus, PaymentWay


class OrderShippingDetailsCreate(BaseModel):
    guest_email: EmailStr = Field(max_length=255)
    guest_phone: str = Field(max_length=20)
    region: str = Field(max_length=100)
    city: str = Field(max_length=100)
    delivery_service: str = Field(max_length=50)
    postal_address: str


class OrderCreate(BaseModel):
    good_id: int

    idempotency_key: uuid.UUID

    payment_type: PaymentWay
    quantity: int = Field(ge=1)

    order_details: OrderShippingDetailsCreate


class OrderResponse(BaseModel):
    id: uuid.UUID

    global_status: OrderGlobalStatus

    model_config = {"from_attributes": True}
