import structlog
from arq import ArqRedis
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.order import Order
from db.models.order_shipping_detail import OrderShippingDetail
from db.models.user import User
from db.repositories.good import GoodRepository
from db.repositories.order import OrderRepository
from schemas.order import OrderCreate

logger = structlog.get_logger("saga.service.order")


class OrderService:
    def __init__(self, session: AsyncSession) -> None:
        self._order_repo = OrderRepository(session)
        self._good_repo = GoodRepository(session)
        self._session = session

    async def create(self, redis: ArqRedis, data: OrderCreate, optional_user: User | None) -> Order:
        good = await self._good_repo.get(data.good_id)
        if good is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Good not found.")

        shipping_data = data.order_details.model_dump()
        # mode="json" serializes uuid.UUID → str, which matches Mapped[str255]
        order_data = data.model_dump(exclude={"order_details"}, mode="json")

        shipping_detail = OrderShippingDetail(**shipping_data)

        new_order = Order(
            **order_data,
            price=good.price,
            buyer_id=optional_user.id if optional_user else None,
            shipping_detail=shipping_detail,
        )

        saved_order = await self._order_repo.create(new_order)
        # Capture id before commit — SQLAlchemy expires all attributes after
        # commit, and accessing them lazily in an async context raises an error.
        order_id = saved_order.id

        logger.info(
            "order.created",
            order_id=str(order_id),
            good_id=str(data.good_id),
            user_id=str(optional_user.id) if optional_user else None,
        )

        # Commit first — only enqueue after the order is persisted.
        # If enqueue fails, the order is still safe in the DB and can be
        # recovered by the scheduler's stuck-order compensation logic.
        await self._session.commit()

        await redis.enqueue_job("process_billing", order_id, _job_id=f"billing_{order_id}")
        logger.info(
            "order.job.enqueued",
            job="process_billing",
            order_id=str(order_id),
        )

        return saved_order
