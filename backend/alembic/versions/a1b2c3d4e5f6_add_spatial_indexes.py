"""add_spatial_indexes

Revision ID: a1b2c3d4e5f6
Revises: 31441228492d
Create Date: 2026-04-04 20:00:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "31441228492d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_locations_geom ON locations USING GIST (geom)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_linear_features_geom ON linear_features USING GIST (geom)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_locations_geom")
    op.execute("DROP INDEX IF EXISTS idx_linear_features_geom")
