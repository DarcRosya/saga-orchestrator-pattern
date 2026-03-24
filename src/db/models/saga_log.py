from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base
from src.db.models.types import created_at_col, str20, str50, uuidpk

if TYPE_CHECKING:
    from src.db.models.order import Order


class SagaLog(Base):
    __tablename__ = "saga_logs"

    id: Mapped[uuidpk]
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"))
    action: Mapped[str50]
    status: Mapped[str20]
    error_details: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[created_at_col]

    # ── Relationships ─────────────────────────────────────────────────────────
    order: Mapped[Order] = relationship(back_populates="saga_logs")
