from datetime import datetime

from pydantic import BaseModel, Field

from db.models.enums import UserPrivileges


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=20)
    password: str = Field(min_length=8)
    email: str | None = None


class LoginRequest(BaseModel):
    username: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: int
    username: str
    email: str | None
    role: UserPrivileges
    created_at: datetime

    model_config = {"from_attributes": True}


class TokenUser(BaseModel):
    id: int
