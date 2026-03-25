import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from src.schemas.auth import LoginRequest, RegisterRequest
from src.services.user import UserService


@pytest.mark.asyncio
async def test_user_service_register_and_login(db_session: AsyncSession):
    # Arrange
    service = UserService(db_session)
    register_req = RegisterRequest(username="servicetest", password="StrongPassword123")

    # Act - Register
    user, access_token, refresh_token = await service.register(register_req)

    # Assert
    assert user is not None
    assert user.username == "servicetest"
    assert access_token is not None
    assert refresh_token is not None

    # Act - Login
    login_req = LoginRequest(username="servicetest", password="StrongPassword123")
    user_login, login_acc, login_ref = await service.login(login_req)

    # Assert
    assert user_login.id == user.id
    assert login_acc is not None

    # Fast failure on wrong password
    with pytest.raises(HTTPException) as exc:
        await service.login(LoginRequest(username="servicetest", password="WrongPassword!!!"))
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_user_service_duplicate_register(db_session: AsyncSession):
    service = UserService(db_session)
    register_req = RegisterRequest(username="dupuser", password="StrongPassword123")
    await service.register(register_req)

    with pytest.raises(HTTPException):
        await service.register(register_req)
