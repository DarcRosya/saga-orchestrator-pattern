from typing import Annotated

from arq import ArqRedis
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import InvalidTokenError

from src.core.database import DBSession
from src.db.models.user import User
from src.schemas.auth import TokenUser
from src.utils.jwt import TokenType, decode_token

_bearer = HTTPBearer(auto_error=False)


async def _resolve_token(token: str) -> TokenUser:
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
) -> TokenUser:
    """Require a valid Bearer access token. Raises 401 if missing or invalid."""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return await _resolve_token(credentials.credentials)


async def get_optional_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> TokenUser | None:
    """Return the authenticated user, or None if no token was provided.
    Raises 401 if a token was provided but is invalid/expired."""
    if not credentials:
        return None
    return await _resolve_token(credentials.credentials)


async def get_redis_pool(request: Request) -> ArqRedis:
    return request.app.state.redis_pool


CurrentUser = Annotated[User, Depends(get_current_user)]
OptionalCurrentUser = Annotated[User | None, Depends(get_optional_current_user)]

RedisClient = Annotated[ArqRedis, Depends(get_redis_pool)]
