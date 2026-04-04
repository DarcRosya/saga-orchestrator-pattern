from .order import admin_router
from .order import router as order_router
from .user import router as user_router


def include_routers(app):  # type: ignore
    app.include_router(order_router)  # type: ignore
    app.include_router(admin_router)  # type: ignore
    app.include_router(user_router)  # type: ignore
