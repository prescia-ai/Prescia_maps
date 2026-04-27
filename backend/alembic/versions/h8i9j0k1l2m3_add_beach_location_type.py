"""Add beach location type

Revision ID: h8i9j0k1l2m3
Revises: a2b3c4d5e6f7
Create Date: 2026-04-22 18:45:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "h8i9j0k1l2m3"
down_revision: Union[str, None] = "g7h8i9j0k1l2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE location_type_enum ADD VALUE IF NOT EXISTS 'beach'")


def downgrade() -> None:
    # PostgreSQL does not support removing values from enums easily.
    # This is a no-op downgrade; the enum value will remain.
    pass
