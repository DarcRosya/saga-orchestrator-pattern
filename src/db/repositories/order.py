from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.enums import SagaStatus
from db.models.order import Order

IN_PROGRESS_STATUSES: tuple[SagaStatus, ...] = (
    SagaStatus.BILLING_STARTED,
    SagaStatus.BILLING_COMPLETED,
    SagaStatus.INVENTORY_STARTED,
    SagaStatus.INVENTORY_COMPLETED,
    SagaStatus.LOGISTICS_STARTED,
)


class OrderRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_pending_orders(self, timeout_seconds: int = 30) -> list[Order]:
        """Return PENDING orders whose updated_at is older than *timeout_seconds*.

        The timeout guards against re-enqueuing an order that was just created
        and is already being picked up by a previous scheduler tick.
        """
        threshold = datetime.now(UTC) - timedelta(seconds=timeout_seconds)
        result = await self._session.execute(
            select(Order).where(
                Order.status == SagaStatus.PENDING,
                Order.updated_at < threshold,
            )
        )
        return list(result.scalars().all())

    async def get_stuck_orders(self, timeout_seconds: int = 60) -> list[Order]:
        """Return in-progress orders whose updated_at is older than *timeout_seconds*.

        These orders started a saga step but never advanced - a sign that the
        responsible worker crashed or timed out and compensation must be triggered.
        """
        threshold = datetime.now(UTC) - timedelta(seconds=timeout_seconds)
        result = await self._session.execute(
            select(Order).where(
                Order.status.in_(IN_PROGRESS_STATUSES),
                Order.updated_at < threshold,
            )
        )
        return list(result.scalars().all())
