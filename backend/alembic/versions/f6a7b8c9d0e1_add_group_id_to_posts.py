"""Add group_id column to posts table

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-04-11 21:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision: str = "f6a7b8c9d0e1"
down_revision: Union[str, None] = "e5f6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "posts",
        sa.Column("group_id", UUID(as_uuid=True), nullable=True),
    )
    op.create_index("ix_posts_group_id", "posts", ["group_id"])


def downgrade() -> None:
    op.drop_index("ix_posts_group_id", table_name="posts")
    op.drop_column("posts", "group_id")
