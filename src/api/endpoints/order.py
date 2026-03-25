from fastapi import APIRouter, Response, status

from src.api.dependencies import OptionalCurrentUser, RedisClient
from src.core.database import DBSession
from src.core.exceptions import DuplicateOrderError
from src.db.models.order import Order
from src.schemas.order import OrderCreate, OrderResponse
from src.services.order import OrderService

router = APIRouter(prefix="/order", tags=["Order"])


@router.post(
    "/",
    response_model=OrderResponse | list[OrderResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create(
    order_details: OrderCreate | list[OrderCreate],
    db: DBSession,
    redis: RedisClient,
    optional_current_user: OptionalCurrentUser,
    response: Response,
) -> Order | list[Order]:
    service = OrderService(db)
    try:
        is_single = isinstance(order_details, OrderCreate)
        data_list = [order_details] if is_single else order_details

        result = await service.create_bulk(
            redis=redis, data_list=data_list, optional_user=optional_current_user
        )
        return result[0] if is_single else result
    except DuplicateOrderError as exc:
        response.status_code = status.HTTP_200_OK
        return exc.existing_order
