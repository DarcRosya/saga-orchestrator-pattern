import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from jwt import InvalidTokenError

from src.api import dependencies
from src.utils.jwt import TokenType


@pytest.mark.asyncio
async def test_get_optional_current_user_without_credentials_returns_none() -> None:
    user = await dependencies.get_optional_current_user(None)
    assert user is None


@pytest.mark.asyncio
async def test_get_current_user_requires_token() -> None:
    with pytest.raises(HTTPException) as exc_info:
        await dependencies.get_current_user(None)

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Authentication required."


@pytest.mark.asyncio
async def test_get_optional_current_user_invalid_token_raises_401(monkeypatch) -> None:
    def fake_decode_token(_: str):
        raise InvalidTokenError("invalid")

    monkeypatch.setattr(dependencies, "decode_token", fake_decode_token)
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="bad-token")

    with pytest.raises(HTTPException) as exc_info:
        await dependencies.get_optional_current_user(credentials)

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Invalid or expired token."


@pytest.mark.asyncio
async def test_get_optional_current_user_requires_access_token(monkeypatch) -> None:
    monkeypatch.setattr(
        dependencies,
        "decode_token",
        lambda _: {"type": TokenType.REFRESH, "sub": "7"},
    )
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="refresh-token")

    with pytest.raises(HTTPException) as exc_info:
        await dependencies.get_optional_current_user(credentials)

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Not an access token."


@pytest.mark.asyncio
async def test_get_optional_current_user_requires_sub_claim(monkeypatch) -> None:
    monkeypatch.setattr(
        dependencies,
        "decode_token",
        lambda _: {"type": TokenType.ACCESS},
    )
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="token-no-sub")

    with pytest.raises(HTTPException) as exc_info:
        await dependencies.get_optional_current_user(credentials)

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Malformed token."


@pytest.mark.asyncio
async def test_get_current_user_returns_token_user(monkeypatch) -> None:
    monkeypatch.setattr(
        dependencies,
        "decode_token",
        lambda _: {"type": TokenType.ACCESS, "sub": "42"},
    )
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="access-token")

    user = await dependencies.get_current_user(credentials)

    assert user.id == 42
