from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import Base
from db.models.enums import PaymentWay, SagaStatus
from db.models.types import (
    created_at_col,
    numeric_10_2,
    str255,
    updated_at_col,
    uuidpk,
)

if TYPE_CHECKING:
    from db.models.good import Good
    from db.models.order_shipping_detail import OrderShippingDetail
    from db.models.saga_log import SagaLog
    from db.models.user import User


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[uuidpk]

    buyer_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"))
    good_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("goods.id"))

    status: Mapped[SagaStatus] = mapped_column(default=SagaStatus.PENDING)

    idempotency_key: Mapped[str255] = mapped_column(unique=True)

    payment_type: Mapped[PaymentWay]
    price: Mapped[numeric_10_2]
    quantity: Mapped[int] = mapped_column(Integer)

    created_at: Mapped[created_at_col]
    updated_at: Mapped[updated_at_col]

    # ── Relationships ─────────────────────────────────────────────────────────
    buyer: Mapped[User] = relationship(back_populates="orders")
    good: Mapped[Good] = relationship(back_populates="orders")
    shipping_detail: Mapped[OrderShippingDetail | None] = relationship(
        back_populates="order", uselist=False
    )
    saga_logs: Mapped[list[SagaLog]] = relationship(
        back_populates="order", order_by="SagaLog.created_at"
    )

    def __repr__(self) -> str:
        return f"<Order id={self.id} status={self.status} buyer_id={self.buyer_id}>"
