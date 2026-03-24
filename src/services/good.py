from sqlalchemy.ext.asyncio import AsyncSession

from db.models.good import Good
from db.repositories.good import GoodRepository


class GoodService:
    def __init__(self, session: AsyncSession) -> None:
        self._good_repo = GoodRepository(session)
        self._session = session

    async def get(self, good_id: int) -> Good | None:
        return await self._good_repo.get(good_id)

    async def create(self, name: str, price: float) -> Good:
        good = Good(name=name, price=price)
        self._session.add(good)
        await self._session.flush()
        await self._session.refresh(good)
        return good
