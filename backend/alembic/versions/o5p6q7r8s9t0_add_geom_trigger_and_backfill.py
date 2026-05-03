"""Add geom trigger and backfill NULL geom values for locations

Revision ID: o5p6q7r8s9t0
Revises: n4o5p6q7r8s9
Create Date: 2026-05-03 00:10:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "o5p6q7r8s9t0"
down_revision: Union[str, None] = "n4o5p6q7r8s9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create the trigger function that auto-populates geom from lat/lon
    op.execute("""
        CREATE OR REPLACE FUNCTION sync_location_geom() RETURNS trigger AS $$
        BEGIN
            IF NEW.geom IS NULL AND NEW.latitude IS NOT NULL AND NEW.longitude IS NOT NULL THEN
                NEW.geom := ST_SetSRID(ST_MakePoint(NEW.longitude, NEW.latitude), 4326);
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    # Attach the trigger to the locations table
    op.execute("""
        DROP TRIGGER IF EXISTS trg_sync_location_geom ON locations;
    """)
    op.execute("""
        CREATE TRIGGER trg_sync_location_geom
        BEFORE INSERT OR UPDATE ON locations
        FOR EACH ROW EXECUTE FUNCTION sync_location_geom();
    """)

    # One-shot backfill: populate geom for all existing rows with valid lat/lon
    op.execute("""
        UPDATE locations
        SET geom = ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)
        WHERE geom IS NULL AND latitude IS NOT NULL AND longitude IS NOT NULL;
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_sync_location_geom ON locations;")
    op.execute("DROP FUNCTION IF EXISTS sync_location_geom();")
