import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Response, status

from src.api.dependencies import OptionalCurrentUser, RedisClient, VerifiedAdmin
from src.core.database import DBSession
from src.core.exceptions import DuplicateOrderError
from src.db.models.enums import OrderGlobalStatus
from src.db.models.order import Order
from src.schemas.order import OrderCreate, OrderResponse
from src.services.order import OrderService

router = APIRouter(prefix="/orders", tags=["Order"])
admin_router = APIRouter(prefix="/admin/orders", tags=["Admin Order"])


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


@admin_router.patch(path="/{order_id}/force-cancel", status_code=status.HTTP_200_OK)
async def force_cancel(
    order_id: uuid.UUID,
    db: DBSession,
    current_admin: VerifiedAdmin,
) -> dict[str, Any]:
    service = OrderService(db)

    order = await service.get(str(order_id))
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    if order.global_status != OrderGlobalStatus.MANUAL_INTERVENTION_REQUIRED:
        raise HTTPException(
            status_code=400,
            detail=f"Order is in {order.global_status} state, not MANUAL_INTERVENTION_REQUIRED",
        )

    await service.update_global_status(str(order_id), OrderGlobalStatus.CANCELLED)
    return {
        "message": f"Order {order_id} forcefully cancelled by admin {current_admin.id}",
        "order_id": order_id,
        "status": OrderGlobalStatus.CANCELLED,
    }
