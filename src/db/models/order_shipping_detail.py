from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import Base
from db.models.types import str20, str50, str100, str255

if TYPE_CHECKING:
    from db.models.order import Order


class OrderShippingDetail(Base):
    __tablename__ = "order_shipping_details"

    # PK == FK → strict 1-to-1 at DB level
    order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("orders.id"), primary_key=True
    )

    guest_email: Mapped[str255]
    guest_phone: Mapped[str20]
    region: Mapped[str100]
    city: Mapped[str100]
    delivery_service: Mapped[str50]
    postal_address: Mapped[str] = mapped_column(Text)

    # ── Relationships ─────────────────────────────────────────────────────────
    order: Mapped[Order] = relationship(back_populates="shipping_detail")
