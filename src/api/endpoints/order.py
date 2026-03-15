from fastapi import APIRouter, Response, status

from api.dependencies import OptionalCurrentUser, RedisClient
from core.database import DBSession
from core.exceptions import DuplicateOrderError
from db.models.order import Order
from schemas.order import OrderCreate, OrderResponse
from services.order import OrderService

router = APIRouter(prefix="/order", tags=["Order"])


@router.post("/", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
async def create(
    order_details: OrderCreate,
    db: DBSession,
    redis: RedisClient,
    optional_current_user: OptionalCurrentUser,
    response: Response,
) -> Order:
    service = OrderService(db)
    try:
        return await service.create(
            redis=redis, data=order_details, optional_user=optional_current_user
        )
    except DuplicateOrderError as exc:
        response.status_code = status.HTTP_200_OK
        return exc.existing_order
