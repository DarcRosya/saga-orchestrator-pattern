from fastapi import APIRouter, status

from api.dependencies import CurrentUser
from core.database import DBSession
from schemas.auth import LoginRequest, RefreshRequest, RegisterRequest, TokenResponse, UserResponse
from services.user import UserService

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, session: DBSession) -> TokenResponse:
    service = UserService(session)
    _, access_token, refresh_token = await service.register(body)
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, session: DBSession) -> TokenResponse:
    service = UserService(session)
    _, access_token, refresh_token = await service.login(body)
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: RefreshRequest, session: DBSession) -> TokenResponse:
    service = UserService(session)
    access_token, refresh_token = await service.refresh_tokens(body.refresh_token)
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(body: RefreshRequest, session: DBSession) -> None:
    service = UserService(session)
    await service.logout(body.refresh_token)


@router.get("/me", response_model=UserResponse)
async def me(current_user: CurrentUser) -> UserResponse:
    return UserResponse.model_validate(current_user)
