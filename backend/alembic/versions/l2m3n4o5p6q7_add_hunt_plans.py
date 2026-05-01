"""Add hunt_plans table

Revision ID: l2m3n4o5p6q7
Revises: k1l2m3n4o5p6
Create Date: 2026-05-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID
from geoalchemy2 import Geometry


# revision identifiers, used by Alembic.
revision: str = "l2m3n4o5p6q7"
down_revision: Union[str, None] = "k1l2m3n4o5p6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create hunt_plan_status_enum type
    op.execute(
        "CREATE TYPE hunt_plan_status_enum AS ENUM ('idea', 'planned', 'done', 'archived')"
    )

    op.create_table(
        "hunt_plans",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "owner_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("planned_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("site_type", sa.String(20), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "idea", "planned", "done", "archived",
                name="hunt_plan_status_enum",
                create_type=False,
            ),
            nullable=False,
            server_default="idea",
        ),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column(
            "geom",
            Geometry("POINT", srid=4326, spatial_index=True),
            nullable=True,
        ),
        sa.Column("area_geojson", JSONB, nullable=False),
        sa.Column("in_zone_markers", JSONB, nullable=True),
        sa.Column("gear_checklist", JSONB, nullable=True),
        sa.Column("permission", JSONB, nullable=True),
        sa.Column("view_snapshot", JSONB, nullable=True),
        sa.Column("photo_urls", JSONB, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_index("ix_hunt_plans_owner_id", "hunt_plans", ["owner_id"])


def downgrade() -> None:
    op.drop_index("ix_hunt_plans_owner_id", table_name="hunt_plans")
    op.drop_table("hunt_plans")
    op.execute("DROP TYPE hunt_plan_status_enum")
