"""Add homestead_site to location_type_enum

Revision ID: j0k1l2m3n4o5
Revises: i9j0k1l2m3n4
Create Date: 2026-04-30 19:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "j0k1l2m3n4o5"
down_revision: Union[str, None] = "i9j0k1l2m3n4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE location_type_enum ADD VALUE IF NOT EXISTS 'homestead_site'")


def downgrade() -> None:
    # PostgreSQL does not support removing values from enums easily.
    # This is a no-op downgrade; the enum value will remain.
    pass
