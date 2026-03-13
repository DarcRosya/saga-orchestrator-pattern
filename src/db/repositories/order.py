from datetime import UTC, datetime, timedelta

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.enums import OrderGlobalStatus, SagaStepStatus
from db.models.order import Order


class OrderRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_stuck_orders_for_compensation(self, timeout_seconds: int = 60) -> list[Order]:
        """
        Searches for orders that are stuck in the “PROCESSING” stage,
        but where one of the specific steps has been stuck in “PENDING” for too long.
        """
        threshold = datetime.now(UTC) - timedelta(seconds=timeout_seconds)

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
