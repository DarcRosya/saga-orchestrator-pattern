from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy.orm import Mapped, relationship

from core.database import Base
from db.models.types import bigintpk, numeric_10_2, str250

if TYPE_CHECKING:
    from db.models.order import Order


class Good(Base):
    __tablename__ = "goods"

    id: Mapped[bigintpk]
    name: Mapped[str250]
    price: Mapped[numeric_10_2]

    # ── Relationships ─────────────────────────────────────────────────────────
    orders: Mapped[list[Order]] = relationship(back_populates="good")
