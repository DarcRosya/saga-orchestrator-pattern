from datetime import UTC, datetime, timedelta

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.enums import OrderGlobalStatus, SagaStepStatus
from src.db.models.order import Order


class OrderRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, order_id: str) -> Order | None:
        stmt = select(Order).where(Order.id == order_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def update_global_status(self, order_id: str, status: OrderGlobalStatus) -> Order | None:
        order = await self.get(order_id)
        if order:
            order.global_status = status
            await self._session.flush()
        return order

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
                (Order.global_status == OrderGlobalStatus.PROCESSING)
                & or_(
                    Order.billing_status == SagaStepStatus.PENDING,
                    Order.inventory_status == SagaStepStatus.PENDING,
                    Order.logistics_status == SagaStepStatus.PENDING,
                ),
                # Stuck compensating and something is still SUCCESS
                (Order.global_status == OrderGlobalStatus.COMPENSATING)
                & or_(
                    Order.billing_status == SagaStepStatus.SUCCESS,
                    Order.inventory_status == SagaStepStatus.SUCCESS,
                    Order.logistics_status == SagaStepStatus.SUCCESS,
                ),
            ),
            Order.updated_at < threshold,
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_existing_by_idempotency_keys(self, keys: list[str]) -> list[Order]:
        stmt = select(Order).where(Order.idempotency_key.in_(keys))
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def create_bulk(self, orders: list[Order]) -> tuple[list[Order], list[Order]]:
        keys = [str(o.idempotency_key) for o in orders]

        existing_orders = await self.get_existing_by_idempotency_keys(keys)
        existing_keys = {str(e.idempotency_key) for e in existing_orders}

        new_orders = [o for o in orders if str(o.idempotency_key) not in existing_keys]

        if new_orders:
            self._session.add_all(new_orders)
            await self._session.flush()
            for order in new_orders:
                await self._session.refresh(order)

        return new_orders, existing_orders
