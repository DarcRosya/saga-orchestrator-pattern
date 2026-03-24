from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base
from src.db.models.enums import UserPrivileges
from src.db.models.types import bigintpk, created_at_col, str20, str255

if TYPE_CHECKING:
    from src.db.models.order import Order
    from src.db.models.refresh_token import RefreshToken


class User(Base):
    __tablename__ = "users"

    id: Mapped[bigintpk]
    username: Mapped[str20] = mapped_column(unique=True)
    email: Mapped[str255 | None] = mapped_column(unique=True, default=None)
    password_hash: Mapped[str255]

    slack_account: Mapped[str | None] = mapped_column(String, unique=True, default=None)
    role: Mapped[UserPrivileges] = mapped_column(default=UserPrivileges.USER)
    created_at: Mapped[created_at_col]

    # ── Relationships ─────────────────────────────────────────────────────────
    orders: Mapped[list[Order]] = relationship(back_populates="buyer")
    refresh_tokens: Mapped[list[RefreshToken]] = relationship(back_populates="user")
