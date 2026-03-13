"""
Public surface of the db.models package.

Import from here instead of from individual modules so that all ORM
classes are registered on Base.metadata before Alembic or the engine
sees it — ordering matters for FK resolution.
"""

from db.models.enums import OrderGlobalStatus, PaymentWay, SagaStepStatus, UserPrivileges
from db.models.good import Good
from db.models.order_shipping_detail import OrderShippingDetail
from db.models.refresh_token import RefreshToken
from db.models.saga_log import SagaLog
from db.models.types import (
    bigintpk,
    created_at_col,
    intpk,
    numeric_10_2,
    servise_status,
    str20,
    str50,
    str64,
    str100,
    str250,
    str255,
    updated_at_col,
    uuidpk,
)
from db.models.user import User
from db.models.order import Order

__all__ = [
    # enums
    "OrderGlobalStatus",
    "SagaStepStatus",
    "UserPrivileges",
    "PaymentWay",
    # models
    "User",
    "Good",
    "Order",
    "OrderShippingDetail",
    "SagaLog",
    "RefreshToken",
    # type aliases (re-exported for convenience)
    "intpk",
    "uuidpk",
    "bigintpk",
    "str20",
    "str50",
    "str64",
    "str100",
    "str250",
    "str255",
    "numeric_10_2",
    "servise_status",
    "created_at_col",
    "updated_at_col",
]
