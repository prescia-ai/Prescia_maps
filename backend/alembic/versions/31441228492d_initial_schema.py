"""initial_schema

Revision ID: 31441228492d
Revises:
Create Date: 2026-04-04 18:44:46.000000

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from geoalchemy2 import Geometry

# revision identifiers, used by Alembic.
revision: str = "31441228492d"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable PostGIS extension (idempotent)
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    # --- locations table ---
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'location_type_enum') THEN
                CREATE TYPE location_type_enum AS ENUM (
                    'battle', 'camp', 'railroad_stop', 'trail', 'town', 'mine',
                    'structure', 'event', 'church', 'school', 'cemetery',
                    'fairground', 'ferry', 'stagecoach_stop', 'spring', 'locale'
                );
            END IF;
        END$$;
        """
    )

    op.create_table(
        "locations",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.Text, nullable=False, index=True),
        sa.Column(
            "type",
            sa.Enum(
                "battle", "camp", "railroad_stop", "trail", "town", "mine",
                "structure", "event", "church", "school", "cemetery",
                "fairground", "ferry", "stagecoach_stop", "spring", "locale",
                name="location_type_enum",
                create_type=False,
            ),
            nullable=False,
            index=True,
        ),
        sa.Column("latitude", sa.Float, nullable=False),
        sa.Column("longitude", sa.Float, nullable=False),
        sa.Column("year", sa.Integer, nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("source", sa.Text, nullable=True),
        sa.Column("confidence", sa.Float, nullable=False, server_default="0.5"),
        sa.Column(
            "geom",
            Geometry("POINT", srid=4326),
            nullable=True,
        ),
    )

    # --- linear_features table ---
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'linear_feature_type_enum') THEN
                CREATE TYPE linear_feature_type_enum AS ENUM (
                    'trail', 'railroad', 'water', 'road'
                );
            END IF;
        END$$;
        """
    )

    op.create_table(
        "linear_features",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.Text, nullable=False, index=True),
        sa.Column(
            "type",
            sa.Enum(
                "trail", "railroad", "water", "road",
                name="linear_feature_type_enum",
                create_type=False,
            ),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "geom",
            Geometry("LINESTRING", srid=4326),
            nullable=True,
        ),
        sa.Column("source", sa.Text, nullable=True),
    )

    # --- map_layers table ---
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'map_layer_type_enum') THEN
                CREATE TYPE map_layer_type_enum AS ENUM (
                    'usgs', 'railroad', 'trail', 'mining'
                );
            END IF;
        END$$;
        """
    )

    op.create_table(
        "map_layers",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column(
            "type",
            sa.Enum(
                "usgs", "railroad", "trail", "mining",
                name="map_layer_type_enum",
                create_type=False,
            ),
            nullable=False,
            index=True,
        ),
        sa.Column("url", sa.Text, nullable=False),
        sa.Column("metadata", sa.JSON, nullable=True),
    )


def downgrade() -> None:
    op.drop_table("map_layers")
    op.drop_table("linear_features")
    op.drop_table("locations")
    op.execute("DROP TYPE IF EXISTS map_layer_type_enum")
    op.execute("DROP TYPE IF EXISTS linear_feature_type_enum")
    op.execute("DROP TYPE IF EXISTS location_type_enum")
