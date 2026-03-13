import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated

import uuid6
from sqlalchemy import BigInteger, Numeric, String, Uuid, func
from sqlalchemy.orm import mapped_column

from db.models.enums import SagaStepStatus

# ── Primary key ───────────────────────────────────────────────────────────────

intpk = Annotated[int, mapped_column(primary_key=True)]
bigintpk = Annotated[int, mapped_column(BigInteger, primary_key=True)]
uuidpk = Annotated[
    uuid.UUID, mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid6.uuid7)
]

# ── Fixed-length / bounded strings ────────────────────────────────────────────

str20 = Annotated[str, mapped_column(String(20))]
str50 = Annotated[str, mapped_column(String(50))]
str64 = Annotated[str, mapped_column(String(64))]
str100 = Annotated[str, mapped_column(String(100))]
str250 = Annotated[str, mapped_column(String(250))]
str255 = Annotated[str, mapped_column(String(255))]

# ── Numeric / money ───────────────────────────────────────────────────────────

numeric_10_2 = Annotated[Decimal, mapped_column(Numeric(10, 2))]

# ── Timestamp helpers ─────────────────────────────────────────────────────────

# Set once by the DB on INSERT.
created_at_col = Annotated[
    datetime,
    mapped_column(server_default=func.now()),
]

# Set by DB on INSERT; updated by the ORM layer on every flush/UPDATE.
# NOTE: for a pure-DB trigger approach add a PostgreSQL trigger separately.
updated_at_col = Annotated[
    datetime,
    mapped_column(server_default=func.now(), onupdate=func.now()),
]


# ── Other ─────────────────────────────────────────────────────────

servise_status = Annotated[SagaStepStatus, mapped_column(default="PENDING")]
