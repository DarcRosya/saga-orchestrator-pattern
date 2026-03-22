from datetime import UTC, datetime, timedelta

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import DuplicateOrderError
from db.models.enums import OrderGlobalStatus, SagaStepStatus
from db.models.order import Order


class OrderRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_stuck_orders_for_compensation(self, timeout_seconds: int = 60) -> list[Order]:
        """
        Searches for orders that are stuck in the "PROCESSING" stage,
        but where one of the specific steps has been stuck in "PENDING" for too long.
        """
        # Remove timezone info to match PostgreSQL TIMESTAMP WITHOUT TIME ZONE
        threshold = datetime.now(UTC).replace(tzinfo=None) - timedelta(seconds=timeout_seconds)

        stmt = select(Order).where(
            Order.global_status == OrderGlobalStatus.PROCESSING,
            Order.updated_at < threshold,
            or_(
                Order.billing_status == SagaStepStatus.PENDING,
                Order.inventory_status == SagaStepStatus.PENDING,
                Order.logistics_status == SagaStepStatus.PENDING,
                Order.billing_status == SagaStepStatus.COMPENSATING,
                # ... add checks for pending compensation here (maybe)
            ),
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_existing_by_idempotency_key(self, key: str) -> Order:
        stmt = select(Order).where(Order.idempotency_key == key)
        result = await self._session.execute(stmt)
        return result.scalar_one()

    async def create(self, order: Order) -> Order:
        idempotency_key = str(order.idempotency_key)
        self._session.add(order)
        try:
            # `flush` sends an SQL query to the database but does not commit the transaction.
            # This is where the database checks `unique=True` for `idempotency_key`
            await self._session.flush()
            await self._session.refresh(order)
            return order
        except IntegrityError:
            # Rollback is required to recover the session after a failed flush.
            await self._session.rollback()
            existing = await self.get_existing_by_idempotency_key(idempotency_key)
            raise DuplicateOrderError(existing) from None
