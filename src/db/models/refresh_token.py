from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import Base
from db.models.types import created_at_col, intpk, str64

if TYPE_CHECKING:
    from db.models.user import User


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[intpk]
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    jti: Mapped[str64] = mapped_column(unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[created_at_col]
    is_revoked: Mapped[bool] = mapped_column(Boolean, default=False)

    # ── Relationships ─────────────────────────────────────────────────────────
    user: Mapped[User] = relationship(back_populates="refresh_tokens")
