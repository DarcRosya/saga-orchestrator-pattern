from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from jwt import InvalidTokenError
from sqlalchemy.ext.asyncio import AsyncSession

from core.settings import settings
from db.models.user import User
from db.repositories.refresh_token import RefreshTokenRepository
from db.repositories.user import UserRepository
from schemas.auth import LoginRequest, RegisterRequest
from utils.jwt import TokenType, create_access_token, create_refresh_token, decode_token
from utils.security import hash_password, verify_password


class UserService:
    def __init__(self, session: AsyncSession) -> None:
        self._user_repo = UserRepository(session)
        self._token_repo = RefreshTokenRepository(session)
        self._session = session

    async def register(self, data: RegisterRequest) -> tuple[User, str, str]:
        if await self._user_repo.get_by_username(data.username):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Username already taken.",
            )
        if data.email and await self._user_repo.get_by_email(data.email):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already registered.",
            )

        user = await self._user_repo.create(
            username=data.username,
            password_hash=hash_password(data.password),
            email=data.email,
        )

        access_token, _ = create_access_token(user.id)
        refresh_token, jti = create_refresh_token(user.id)
        expires_at = datetime.now(UTC) + timedelta(days=settings.auth.REFRESH_TOKEN_EXPIRE_DAYS)
        await self._token_repo.create(user.id, jti, expires_at)

        await self._session.commit()
        return user, access_token, refresh_token

    async def login(self, data: LoginRequest) -> tuple[User, str, str]:
        user = await self._user_repo.get_by_username(data.username)
        if not user or not verify_password(data.password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid username or password.",
            )

        access_token, _ = create_access_token(user.id)
        refresh_token, jti = create_refresh_token(user.id)
        expires_at = datetime.now(UTC) + timedelta(days=settings.auth.REFRESH_TOKEN_EXPIRE_DAYS)
        await self._token_repo.create(user.id, jti, expires_at)

        await self._session.commit()
        return user, access_token, refresh_token

    async def refresh_tokens(self, token: str) -> tuple[str, str]:
        try:
            payload = decode_token(token)
        except InvalidTokenError as err:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired refresh token.",
            ) from err

        if payload.get("type") != TokenType.REFRESH:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not a refresh token.",
            )

        jti: str = payload["jti"]
        stored = await self._token_repo.get_by_jti(jti)
        if not stored or stored.is_revoked:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token has been revoked.",
            )

        user_id = int(payload["sub"])
        await self._token_repo.revoke_by_jti(jti)

        new_access, _ = create_access_token(user_id)
        new_refresh, new_jti = create_refresh_token(user_id)
        expires_at = datetime.now(UTC) + timedelta(days=settings.auth.REFRESH_TOKEN_EXPIRE_DAYS)
        await self._token_repo.create(user_id, new_jti, expires_at)

        await self._session.commit()
        return new_access, new_refresh

    async def logout(self, token: str) -> None:
        try:
            payload = decode_token(token)
        except InvalidTokenError as err:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired refresh token.",
            ) from err

        if payload.get("type") != TokenType.REFRESH:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not a refresh token.",
            )

        jti: str = payload["jti"]
        await self._token_repo.revoke_by_jti(jti)
        await self._session.commit()
