"""Add subscription fields to users table

Revision ID: m3n4o5p6q7r8
Revises: l2m3n4o5p6q7
Create Date: 2026-05-01 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "m3n4o5p6q7r8"
down_revision: Union[str, None] = "l2m3n4o5p6q7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add subscription fields with sensible defaults so existing rows backfill cleanly.
    op.add_column(
        "users",
        sa.Column(
            "subscription_tier",
            sa.String(20),
            nullable=False,
            server_default="free",
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "subscription_status",
            sa.String(20),
            nullable=False,
            server_default="none",
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "subscription_provider",
            sa.String(20),
            nullable=False,
            server_default="none",
        ),
    )
    op.add_column(
        "users",
        sa.Column("subscription_plan", sa.String(20), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("trial_ends_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("canceled_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("stripe_customer_id", sa.String(100), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("stripe_subscription_id", sa.String(100), nullable=True),
    )

    # Create indexes for Stripe ID columns used in webhook lookups
    op.create_index(
        "ix_users_stripe_customer_id",
        "users",
        ["stripe_customer_id"],
    )
    op.create_index(
        "ix_users_stripe_subscription_id",
        "users",
        ["stripe_subscription_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_users_stripe_subscription_id", table_name="users")
    op.drop_index("ix_users_stripe_customer_id", table_name="users")
    op.drop_column("users", "stripe_subscription_id")
    op.drop_column("users", "stripe_customer_id")
    op.drop_column("users", "canceled_at")
    op.drop_column("users", "current_period_end")
    op.drop_column("users", "trial_ends_at")
    op.drop_column("users", "subscription_plan")
    op.drop_column("users", "subscription_provider")
    op.drop_column("users", "subscription_status")
    op.drop_column("users", "subscription_tier")
