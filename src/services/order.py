import asyncio

import structlog
from arq import ArqRedis
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.enums import OrderGlobalStatus
from src.db.models.order import Order
from src.db.models.order_shipping_detail import OrderShippingDetail
from src.db.models.user import User
from src.db.repositories.good import GoodRepository
from src.db.repositories.order import OrderRepository
from src.schemas.order import OrderCreate

logger = structlog.get_logger("saga.service.order")


class OrderService:
    def __init__(self, session: AsyncSession) -> None:
        self._order_repo = OrderRepository(session)
        self._good_repo = GoodRepository(session)
        self._session = session

    async def get(self, order_id: str) -> Order | None:
        return await self._order_repo.get(order_id)

    async def update_global_status(self, order_id: str, status: OrderGlobalStatus) -> Order | None:
        order = await self._order_repo.update_global_status(order_id, status)
        await self._session.commit()
        return order

    async def create(self, redis: ArqRedis, data: OrderCreate, optional_user: User | None) -> Order:
        result = await self.create_bulk(redis, [data], optional_user)
        return result[0]

    async def create_bulk(
        self, redis: ArqRedis, data_list: list[OrderCreate], optional_user: User | None
    ) -> list[Order]:
        good_ids = {d.good_id for d in data_list}
        goods = await self._good_repo.get_many(list(good_ids))
        good_map = {g.id: g for g in goods}

        missing_goods = good_ids - set(good_map.keys())
        if missing_goods:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"Goods not found: {missing_goods}"
            )

        new_orders: list[Order] = []
        for data in data_list:
            shipping_data = data.order_details.model_dump()
            order_data = data.model_dump(exclude={"order_details"}, mode="json")

            shipping_detail = OrderShippingDetail(**shipping_data)
            new_order = Order(
                **order_data,
                buyer_id=optional_user.id if optional_user else None,
                shipping_detail=shipping_detail,
            )
            new_orders.append(new_order)

        saved_orders: list[Order] = await self._order_repo.create_bulk(new_orders)
        await self._session.commit()

        redis_tasks = [
            redis.enqueue_job(
                "process_billing",
                str(order.id),
                _job_id=f"billing_{order.id}",
                _queue_name="saga:tasks",
            )
            for order in saved_orders
        ]
        await asyncio.gather(*redis_tasks)

        for order in saved_orders:
            logger.info(
                "order.created",
                order_id=str(order.id),
                good_id=str(order.good_id),
                user_id=str(optional_user.id) if optional_user else None,
            )
            logger.info(
                "order.job.enqueued",
                category="bulk",
                job="process_billing",
                order_id=str(order.id),
            )

        return saved_orders
