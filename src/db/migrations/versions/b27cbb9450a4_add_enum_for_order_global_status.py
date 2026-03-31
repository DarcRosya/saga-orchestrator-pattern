"""add enum for order global status

Revision ID: b27cbb9450a4
Revises: 070b554fc230
Create Date: 2026-03-31 18:14:35.785185

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b27cbb9450a4"
down_revision: Union[str, Sequence[str], None] = "070b554fc230"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("ALTER TYPE orderglobalstatus ADD VALUE IF NOT EXISTS 'COMPENSATING';")
    op.execute(
        "ALTER TYPE orderglobalstatus ADD VALUE IF NOT EXISTS 'MANUAL_INTERVENTION_REQUIRED';"
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Downgrading enum values is not supported natively in Postgres
    # without recreating the whole enum/table. We'll leave it as a no-op here.
    pass
