import enum


class SagaStatus(str, enum.Enum):
    # ── Happy path ────────────────────────────────────────────────────────────
    PENDING = "PENDING"
    BILLING_STARTED = "BILLING_STARTED"
    BILLING_COMPLETED = "BILLING_COMPLETED"
    INVENTORY_STARTED = "INVENTORY_STARTED"
    INVENTORY_COMPLETED = "INVENTORY_COMPLETED"
    LOGISTICS_STARTED = "LOGISTICS_STARTED"
    COMPLETED = "COMPLETED"

    # ── Compensation (rollback) path ──────────────────────────────────────────
    COMPENSATING_LOGISTICS = "COMPENSATING_LOGISTICS"
    COMPENSATING_INVENTORY = "COMPENSATING_INVENTORY"
    COMPENSATING_BILLING = "COMPENSATING_BILLING"

    # ── Terminal states ───────────────────────────────────────────────────────
    CANCELLED = "CANCELLED"
    REQUIRES_MANUAL_INTERVENTION = "REQUIRES_MANUAL_INTERVENTION"


class UserPrivileges(str, enum.Enum):
    USER = "user"
    ADMIN = "admin"


class PaymentWay(str, enum.Enum):
    PREPAYMENT = "prepayment"
    POSTPAYMENT = "postpayment"
