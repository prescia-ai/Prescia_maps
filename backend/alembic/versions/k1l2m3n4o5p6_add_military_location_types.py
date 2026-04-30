"""Add wwii_training, wwi_training, pow_camp to location_type_enum

Revision ID: k1l2m3n4o5p6
Revises: j0k1l2m3n4o5
Create Date: 2026-04-30 21:30:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "k1l2m3n4o5p6"
down_revision: Union[str, None] = "j0k1l2m3n4o5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE location_type_enum ADD VALUE IF NOT EXISTS 'wwii_training'")
    op.execute("ALTER TYPE location_type_enum ADD VALUE IF NOT EXISTS 'wwi_training'")
    op.execute("ALTER TYPE location_type_enum ADD VALUE IF NOT EXISTS 'pow_camp'")


def downgrade() -> None:
    # PostgreSQL does not support removing values from an enum natively.
    # The values will remain but can safely be ignored if unused.
    pass
