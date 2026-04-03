import asyncio

import structlog
from sqlalchemy import select

from src.core.database import async_session_factory
from src.db.models.good import Good

logger = structlog.get_logger(__name__)


async def seed_goods():
    async with async_session_factory() as session:
        result = await session.execute(select(Good).limit(1))
        if result.scalars().first():
            logger.info("The products already exist. We'll skip the seeding phase.")
            return

        goods = [
            Good(id=1, name="Cyberpunk Coffee", price=5.99),
            Good(id=2, name="Quantum Keyboard", price=120.50),
            Good(id=3, name="Neural Headphones", price=299.99),
            Good(id=4, name="Shit games from Steam", price=3.99),
            Good(id=5, name="Bird toy", price=99.99),
        ]
        session.add_all(goods)
        await session.commit()
        logger.info("The database has been successfully populated with test products!")


if __name__ == "__main__":
    asyncio.run(seed_goods())
