"""
Badge service — checks badge criteria and awards new badges to users.

Supports two criteria types that can be evaluated from existing data:
  - hunt_count:   number of UserPin records for the user
  - finds_count:  sum of UserPin.finds_count for the user

Site-type and score-threshold criteria are stored in the database but
require additional data sources; their check logic is a no-op stub that
can be filled in when the data is available.
"""

from __future__ import annotations

from typing import List
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import Badge, UserBadge, UserPin


async def check_all_badges(user_id: UUID, db: AsyncSession) -> List[Badge]:
    """
    Check all badge criteria for *user_id* and award any newly earned badges.

    Returns a list of Badge objects that were **newly** awarded during this call.
    """
    # Fetch all badges
    result = await db.execute(select(Badge))
    all_badges: List[Badge] = list(result.scalars().all())

    # Fetch already-earned badge IDs for the user
    earned_result = await db.execute(
        select(UserBadge.badge_id).where(UserBadge.user_id == user_id)
    )
    already_earned: set[UUID] = {row[0] for row in earned_result.all()}

    # Compute user stats (only if needed)
    hunt_count: int | None = None
    finds_count: int | None = None

    async def _get_hunt_count() -> int:
        nonlocal hunt_count
        if hunt_count is None:
            r = await db.execute(
                select(func.count()).select_from(UserPin).where(UserPin.user_id == user_id)
            )
            hunt_count = r.scalar() or 0
        return hunt_count

    async def _get_finds_count() -> int:
        nonlocal finds_count
        if finds_count is None:
            r = await db.execute(
                select(func.coalesce(func.sum(UserPin.finds_count), 0)).where(
                    UserPin.user_id == user_id
                )
            )
            finds_count = r.scalar() or 0
        return finds_count

    newly_earned: List[Badge] = []

    for badge in all_badges:
        if badge.id in already_earned:
            continue

        criteria = badge.criteria or {}
        criteria_type = criteria.get("type", "")
        threshold = criteria.get("threshold")

        earned = False

        if criteria_type == "hunt_count" and threshold is not None:
            count = await _get_hunt_count()
            earned = count >= threshold

        elif criteria_type == "finds_count" and threshold is not None:
            count = await _get_finds_count()
            earned = count >= threshold

        elif criteria_type in ("site_type", "score_threshold"):
            # Future implementation — skip for now
            earned = False

        if earned:
            user_badge = UserBadge(user_id=user_id, badge_id=badge.id)
            db.add(user_badge)
            newly_earned.append(badge)

    if newly_earned:
        await db.flush()

    return newly_earned


async def get_badge_progress(user_id: UUID, db: AsyncSession) -> list[dict]:
    """
    Return progress information for every badge for the given user.

    Each dict contains:
      - badge: Badge ORM object
      - earned: bool
      - earned_at: datetime | None
      - current_value: int
      - threshold: int | None
    """
    result = await db.execute(select(Badge))
    all_badges: List[Badge] = list(result.scalars().all())

    earned_result = await db.execute(
        select(UserBadge).where(UserBadge.user_id == user_id)
    )
    earned_map: dict[UUID, UserBadge] = {
        ub.badge_id: ub for ub in earned_result.scalars().all()
    }

    # Pre-compute stats
    hunt_count_result = await db.execute(
        select(func.count()).select_from(UserPin).where(UserPin.user_id == user_id)
    )
    hunt_count = hunt_count_result.scalar() or 0

    finds_count_result = await db.execute(
        select(func.coalesce(func.sum(UserPin.finds_count), 0)).where(
            UserPin.user_id == user_id
        )
    )
    finds_count = finds_count_result.scalar() or 0

    progress_list = []
    for badge in all_badges:
        criteria = badge.criteria or {}
        criteria_type = criteria.get("type", "")
        threshold = criteria.get("threshold")

        if criteria_type == "hunt_count":
            current_value = hunt_count
        elif criteria_type == "finds_count":
            current_value = finds_count
        else:
            current_value = 0

        user_badge = earned_map.get(badge.id)
        earned = user_badge is not None

        progress_list.append(
            {
                "badge": badge,
                "earned": earned,
                "earned_at": user_badge.earned_at if user_badge else None,
                "current_value": current_value,
                "threshold": threshold,
            }
        )

    return progress_list
