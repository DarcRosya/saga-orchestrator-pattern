import os
from collections.abc import AsyncGenerator

import pytest_asyncio
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from src.core.database import Base
from src.core.settings import settings

# Import all models so metadata knows about them
from src.db.models import *  # noqa: F403
from src.db.repositories.good import GoodRepository
from src.db.repositories.order import OrderRepository
from src.services.order import OrderService

TEST_DB_URL = os.getenv(
    "TEST_DATABASE_URL",
    f"postgresql+asyncpg://{settings.db.USER}:{__import__('urllib.parse').parse.quote(settings.db.PASS.get_secret_value())}@127.0.0.1:5434/test_saga_db",
)

test_engine = create_async_engine(TEST_DB_URL, echo=False, poolclass=NullPool)
TestingSessionLocal = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)


@pytest_asyncio.fixture(scope="function")
async def setup_test_db() -> AsyncGenerator[AsyncEngine, None]:
    """Create test database engine (function-scoped, tables created once per test)."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    yield test_engine

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture(scope="function")
async def db_session(setup_test_db: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """Yield a database session. State is isolated by dropping/creating tables per test."""
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        await session.close()


@pytest_asyncio.fixture
async def order_repository(db_session: AsyncSession) -> OrderRepository:
    return OrderRepository(db_session)


@pytest_asyncio.fixture
async def good_repository(db_session: AsyncSession) -> GoodRepository:
    return GoodRepository(db_session)


@pytest_asyncio.fixture
async def order_service(db_session: AsyncSession) -> OrderService:
    return OrderService(db_session)
