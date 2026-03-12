from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import InvalidTokenError
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import DBSession
from db.models.user import User
from schemas.auth import TokenUser
from utils.jwt import TokenType, decode_token

_bearer = HTTPBearer(auto_error=False)


async def _resolve_token(token: str, session: AsyncSession) -> TokenUser:
    try:
        payload = decode_token(token)
    except InvalidTokenError as err:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from err

    if payload.get("type") != TokenType.ACCESS:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not an access token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    sub: str | None = payload.get("sub")
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return TokenUser(id=int(sub))


async def get_current_user(
    session: DBSession,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> User:
    """Require a valid Bearer access token. Raises 401 if missing or invalid."""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return await _resolve_token(credentials.credentials, session)


async def get_optional_current_user(
    session: DBSession,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> User | None:
    """Return the authenticated user, or None if no token was provided.
    Raises 401 if a token was provided but is invalid/expired."""
    if not credentials:
        return None
    return await _resolve_token(credentials.credentials, session)


CurrentUser = Annotated[User, Depends(get_current_user)]
OptionalCurrentUser = Annotated[User | None, Depends(get_optional_current_user)]
