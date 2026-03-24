import secrets
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any

import jwt

from src.core.settings import settings


class TokenType(StrEnum):
    ACCESS = "access"
    REFRESH = "refresh"


def _make_jti() -> str:
    """Generate a 64-char hex string suitable for the jti claim."""
    return secrets.token_hex(32)


def create_access_token(user_id: int) -> tuple[str, str]:
    """Return (encoded_jwt, jti)."""
    jti = _make_jti()
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "jti": jti,
        "type": TokenType.ACCESS,
        "iat": now,
        "exp": now + timedelta(minutes=settings.auth.ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    secret: str = settings.auth.SECRET_KEY.get_secret_value()
    token: str = jwt.encode(payload, secret, algorithm=settings.auth.ALGORITHM)  # type: ignore[reportUnknownMemberType]
    return token, jti


def create_refresh_token(user_id: int) -> tuple[str, str]:
    """Return (encoded_jwt, jti)."""
    jti = _make_jti()
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "jti": jti,
        "type": TokenType.REFRESH,
        "iat": now,
        "exp": now + timedelta(days=settings.auth.REFRESH_TOKEN_EXPIRE_DAYS),
    }
    secret: str = settings.auth.SECRET_KEY.get_secret_value()
    token: str = jwt.encode(payload, secret, algorithm=settings.auth.ALGORITHM)  # type: ignore[reportUnknownMemberType]
    return token, jti


def decode_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT. Raises jwt.InvalidTokenError on any failure."""
    secret: str = settings.auth.SECRET_KEY.get_secret_value()
    return jwt.decode(token, secret, algorithms=[settings.auth.ALGORITHM])  # type: ignore[reportUnknownMemberType]
