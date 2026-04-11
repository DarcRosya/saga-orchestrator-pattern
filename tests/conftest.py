import os
import uuid
from collections.abc import AsyncGenerator
from typing import Any, Callable, Coroutine  # noqa: UP035

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


@pytest_asyncio.fixture(scope="function")  # type: ignore
async def setup_test_db() -> AsyncGenerator[AsyncEngine, None]:
    """Create test database engine (function-scoped, tables created once per test)."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    yield test_engine


@pytest_asyncio.fixture(scope="function")  # type: ignore
async def db_session(setup_test_db: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """Yield a database session. State is isolated by dropping/creating tables per test."""
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        await session.close()


@pytest_asyncio.fixture  # type: ignore
async def order_repository(db_session: AsyncSession) -> OrderRepository:
    return OrderRepository(db_session)


@pytest_asyncio.fixture  # type: ignore
async def good_repository(db_session: AsyncSession) -> GoodRepository:
    return GoodRepository(db_session)


@pytest_asyncio.fixture  # type: ignore
async def order_service(db_session: AsyncSession) -> OrderService:
    return OrderService(db_session)


@pytest_asyncio.fixture  # type: ignore
async def create_setup_order(
    db_session: AsyncSession,
) -> Callable[..., Coroutine[Any, Any, tuple[Order, Good]]]:  # noqa: F405
    """
    A fixture-factory for easily creating a test order alongside the product.
    """

    async def _create(
        good_name: str = "Test Item",
        good_price: float = 100.0,
        quantity: int = 1,
        payment_type: PaymentWay = PaymentWay.PREPAYMENT,  # noqa: F405
        global_status: OrderGlobalStatus = OrderGlobalStatus.PROCESSING,  # noqa: F405
    ) -> tuple[Order, Good]:  # noqa: F405
        good = Good(name=good_name, price=good_price)  # noqa: F405
        db_session.add(good)
        await db_session.flush()

        order_id = uuid.uuid4()
        idempotency_key = str(uuid.uuid4())

        order = Order(  # noqa: F405
            id=order_id,
            good_id=good.id,
            idempotency_key=idempotency_key,
            billing_status=SagaStepStatus.PENDING,  # noqa: F405
            inventory_status=SagaStepStatus.PENDING,  # noqa: F405
            logistics_status=SagaStepStatus.PENDING,  # noqa: F405
            global_status=global_status,
            payment_type=payment_type,
            quantity=quantity,
        )
        db_session.add(order)
        await db_session.commit()
        return order, good

    return _create

@pytest_asyncio.fixture
async def async_client(db_session: AsyncSession) -> Any:
    from fastapi import FastAPI
    from httpx import AsyncClient, ASGITransport
    from src.main import app
    from src.core.database import get_async_session

    app.dependency_overrides[get_async_session] = lambda: db_session
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    
    app.dependency_overrides.clear()

@pytest_asyncio.fixture
def mock_redis(mocker):
    """Mock Redis client for enqueueing jobs."""
    return mocker.AsyncMock()

@pytest_asyncio.fixture
async def api_client(db_session, mock_redis):
    """Provide an AsyncClient configured to use the test database and mock Redis."""
    from httpx import AsyncClient, ASGITransport
    from src.main import app
    from src.core.database import get_async_session
    from src.api.dependencies import get_redis_pool

    async def override_get_session():
        yield db_session
        
    async def override_get_redis_pool():
        return mock_redis

    app.dependency_overrides[get_async_session] = override_get_session
    app.dependency_overrides[get_redis_pool] = override_get_redis_pool

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testServer/api"
    ) as client:
        yield client

    app.dependency_overrides.clear()
