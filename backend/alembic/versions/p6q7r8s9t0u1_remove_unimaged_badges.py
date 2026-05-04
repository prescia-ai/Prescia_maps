"""Remove 5 Treasure Trove badges that have no badge image

Removes Coin Collector, Button Box, Lead Farmer, Jewelry Box, and Buckle Up
badges which have no corresponding image files, causing broken-image placeholders
on the Badges page. Cascades to user_badges rows first (idempotent).

Revision ID: p6q7r8s9t0u1
Revises: o5p6q7r8s9t0
Create Date: 2026-05-04 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "p6q7r8s9t0u1"
down_revision: Union[str, None] = "o5p6q7r8s9t0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# The 5 badge_id values (as stored in the badges.badge_id string column)
_BADGE_IDS_TO_REMOVE = [
    "A1B2C3D4-E5F6-7890-ABCD-EF1234567890",  # Coin Collector
    "B2C3D4E5-F6A7-8901-BCDE-F12345678901",  # Button Box
    "C3D4E5F6-A7B8-9012-CDEF-123456789012",  # Lead Farmer
    "D4E5F6A7-B8C9-0123-DEF0-234567890123",  # Jewelry Box
    "E5F6A7B8-C9D0-1234-EF01-345678901234",  # Buckle Up
]


def upgrade() -> None:
    conn = op.get_bind()

    # Delete user_badge rows first (foreign-key cascade already handles this
    # when ondelete="CASCADE" is set, but we do it explicitly to be idempotent
    # regardless of FK settings).
    conn.execute(
        sa.text(
            "DELETE FROM user_badges "
            "WHERE badge_id IN (SELECT id FROM badges WHERE badge_id = ANY(:ids))"
        ),
        {"ids": _BADGE_IDS_TO_REMOVE},
    )

    # Delete the badge rows themselves
    conn.execute(
        sa.text("DELETE FROM badges WHERE badge_id = ANY(:ids)"),
        {"ids": _BADGE_IDS_TO_REMOVE},
    )


def downgrade() -> None:
    # Restoration of deleted data is not supported in this migration.
    # Re-run scripts/seed_badges.py (after reverting the seed file) to
    # restore these badges if needed.
    pass
