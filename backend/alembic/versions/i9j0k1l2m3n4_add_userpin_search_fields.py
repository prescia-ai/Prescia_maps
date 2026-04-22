"""Add search_pattern and depth_inches to user_pins

Revision ID: i9j0k1l2m3n4
Revises: h8i9j0k1l2m3
Create Date: 2026-04-22 18:46:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "i9j0k1l2m3n4"
down_revision: Union[str, None] = "h8i9j0k1l2m3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("user_pins", sa.Column("search_pattern", sa.String(50), nullable=True))
    op.add_column("user_pins", sa.Column("depth_inches", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("user_pins", "depth_inches")
    op.drop_column("user_pins", "search_pattern")
