"""
Admin statistics endpoint.

Exposes a single read-only endpoint that returns aggregated platform metrics
computed from the ``users`` table.  Access is restricted to admin users.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.admin import require_admin
from app.models.database import User, get_db
from app.models.schemas import AdminStatsResponse

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/stats", response_model=AdminStatsResponse)
async def get_admin_stats(
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> AdminStatsResponse:
    """
    Return aggregated user / subscription metrics.

    Requires admin privileges (``require_admin`` dependency).
    All counts are computed in a single SQL query using conditional aggregation.
    """
    now = datetime.now(timezone.utc)
    cutoff_7d = now - timedelta(days=7)
    cutoff_30d = now - timedelta(days=30)

    pro_statuses = ("trialing", "active")

    result = await db.execute(
        select(
            func.count().label("total_users"),
            func.count(case((User.is_admin.is_(True), 1))).label("admins"),
            func.count(
                case((User.subscription_status.in_(pro_statuses), 1))
            ).label("pro_users"),
            func.count(
                case((User.subscription_status == "trialing", 1))
            ).label("trialing_users"),
            func.count(
                case((User.subscription_status == "active", 1))
            ).label("active_users"),
            func.count(
                case((User.subscription_status == "past_due", 1))
            ).label("past_due_users"),
            func.count(
                case((User.subscription_status == "canceled", 1))
            ).label("canceled_users"),
            func.count(
                case(
                    (
                        User.subscription_plan == "monthly",
                        case((User.subscription_status.in_(pro_statuses), 1)),
                    )
                )
            ).label("plan_monthly"),
            func.count(
                case(
                    (
                        User.subscription_plan == "annual",
                        case((User.subscription_status.in_(pro_statuses), 1)),
                    )
                )
            ).label("plan_annual"),
            func.count(
                case((User.created_at >= cutoff_7d, 1))
            ).label("new_users_7d"),
            func.count(
                case((User.created_at >= cutoff_30d, 1))
            ).label("new_users_30d"),
        )
    )

    row = result.one()

    total_users: int = row.total_users or 0
    admins: int = row.admins or 0
    pro_users: int = row.pro_users or 0
    trialing_users: int = row.trialing_users or 0
    active_users: int = row.active_users or 0
    past_due_users: int = row.past_due_users or 0
    canceled_users: int = row.canceled_users or 0
    plan_monthly: int = row.plan_monthly or 0
    plan_annual: int = row.plan_annual or 0
    new_users_7d: int = row.new_users_7d or 0
    new_users_30d: int = row.new_users_30d or 0

    free_users = max(0, total_users - pro_users - admins)
    conversion_rate = round(pro_users / max(total_users, 1), 4)

    return AdminStatsResponse(
        generated_at=now,
        total_users=total_users,
        admins=admins,
        pro_users=pro_users,
        trialing_users=trialing_users,
        active_users=active_users,
        past_due_users=past_due_users,
        canceled_users=canceled_users,
        free_users=free_users,
        plan_monthly=plan_monthly,
        plan_annual=plan_annual,
        new_users_7d=new_users_7d,
        new_users_30d=new_users_30d,
        conversion_rate=conversion_rate,
    )
