from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.enums import UserPrivileges
from src.db.models.user import User


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, user_id: int) -> User | None:
        return await self._session.get(User, user_id)

    async def get_by_username(self, username: str) -> User | None:
        result = await self._session.execute(select(User).where(User.username == username))
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        result = await self._session.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def check_id_admin_role(self, user_id: int) -> bool:
        result = await self._session.execute(
            select(User).where(User.id == user_id, User.role == UserPrivileges.ADMIN)
        )
        admin = result.scalar_one_or_none()
        return bool(admin)

    async def create(
        self,
        username: str,
        password_hash: str,
        email: str | None = None,
    ) -> User:
        user = User(username=username, password_hash=password_hash, email=email)
        self._session.add(user)
        await self._session.flush()
        await self._session.refresh(user)
        return user
