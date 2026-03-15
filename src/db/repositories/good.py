from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.good import Good


class GoodRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, good_id: int) -> Good | None:
        stmt = select(Good).where(Good.id == good_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()
