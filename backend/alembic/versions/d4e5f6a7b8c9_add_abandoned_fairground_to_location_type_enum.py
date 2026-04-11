"""add abandoned_fairground to location_type_enum

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-04-11 15:30:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE location_type_enum ADD VALUE IF NOT EXISTS 'abandoned_fairground'")


def downgrade() -> None:
    # PostgreSQL does not support removing values from enums easily.
    # This is a no-op downgrade; the enum value will remain.
    pass
