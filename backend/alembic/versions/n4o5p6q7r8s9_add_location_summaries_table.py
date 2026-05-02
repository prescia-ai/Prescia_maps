"""Add location_summaries table for LLM Site Insight cache

Revision ID: n4o5p6q7r8s9
Revises: m3n4o5p6q7r8
Create Date: 2026-05-02 23:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision: str = "n4o5p6q7r8s9"
down_revision: Union[str, None] = "m3n4o5p6q7r8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "location_summaries",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("lat_key", sa.Float, nullable=False),
        sa.Column("lon_key", sa.Float, nullable=False),
        sa.Column("summary", sa.Text, nullable=False),
        sa.Column("model", sa.String(64), nullable=False),
        sa.Column("nearby_signature", sa.String(64), nullable=False),
        sa.Column(
            "generated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("lat_key", "lon_key", name="uq_location_summary_coords"),
    )
    op.create_index(
        "ix_location_summaries_coords",
        "location_summaries",
        ["lat_key", "lon_key"],
    )


def downgrade() -> None:
    op.drop_index("ix_location_summaries_coords", table_name="location_summaries")
    op.drop_table("location_summaries")
