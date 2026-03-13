import enum


class SagaStepStatus(str, enum.Enum):
    PENDING = "PENDING"
    FAILED = "FAILED"
    SUCCESS = "SUCCESS"
    CANCELLED = "CANCELLED"
    COMPENSATING = "COMPENSATING"
    COMPENSATED = "COMPENSATED"
    SKIPPED = "SKIPPED"


class OrderGlobalStatus(str, enum.Enum):
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class UserPrivileges(str, enum.Enum):
    USER = "user"
    ADMIN = "admin"


class PaymentWay(str, enum.Enum):
    PREPAYMENT = "prepayment"
    POSTPAYMENT = "postpayment"
