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
        Or it is in COMPENSATING stage and stuck.
        """
        threshold = datetime.now(UTC).replace(tzinfo=None) - timedelta(seconds=timeout_seconds)

        stmt = select(Order).where(
            or_(
                # Stuck processing and needs initial compensation
                (Order.global_status == OrderGlobalStatus.PROCESSING) & or_(
                    Order.billing_status == SagaStepStatus.PENDING,
                    Order.inventory_status == SagaStepStatus.PENDING,
                    Order.logistics_status == SagaStepStatus.PENDING,
                ),
                # Stuck compensating and something is still SUCCESS
                (Order.global_status == OrderGlobalStatus.COMPENSATING) & or_(
                    Order.billing_status == SagaStepStatus.SUCCESS,
                    Order.inventory_status == SagaStepStatus.SUCCESS,
                    Order.logistics_status == SagaStepStatus.SUCCESS,
                )
            ),
            Order.updated_at < threshold,
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
            await self._session.flush()
            await self._session.refresh(order)
            return order
        except IntegrityError:
            await self._session.rollback()
            existing = await self.get_existing_by_idempotency_key(idempotency_key)
            raise DuplicateOrderError(existing) from None
