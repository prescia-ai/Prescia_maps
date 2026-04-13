"""
Badge service — evaluates badge criteria and awards badges to users.

Currently supports two criteria types that can be evaluated from the
local database without external data:

  - ``hunt_count``:  number of UserPin rows for the user
  - ``finds_count``: sum of UserPin.finds_count for the user

Site-type and score-threshold criteria are modelled in the database but
are not yet auto-awarded (requires location-proximity data at hunt time).
"""

from __future__ import annotations

import uuid
from typing import List, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import Badge, UserBadge, UserPin


async def _get_hunt_count(user_id: uuid.UUID, db: AsyncSession) -> int:
    """Return the total number of hunts logged by the user."""
    result = await db.execute(
        select(func.count()).select_from(UserPin).where(UserPin.user_id == user_id)
    )
    return result.scalar_one() or 0


async def _get_finds_count(user_id: uuid.UUID, db: AsyncSession) -> int:
    """Return the total number of finds recorded by the user."""
    result = await db.execute(
        select(func.coalesce(func.sum(UserPin.finds_count), 0)).where(
            UserPin.user_id == user_id
        )
    )
    return result.scalar_one() or 0


async def check_all_badges(
    user_id: uuid.UUID, db: AsyncSession
) -> List[Badge]:
    """
    Evaluate all badge criteria for *user_id* and award any newly earned badges.

    Returns a list of Badge objects that were **newly** awarded during this call.
    Already-earned badges are skipped (idempotent).
    """
    # Load all badges
    all_badges_result = await db.execute(select(Badge))
    all_badges: List[Badge] = list(all_badges_result.scalars().all())

    # Load badges the user already has
    earned_result = await db.execute(
        select(UserBadge.badge_id).where(UserBadge.user_id == user_id)
    )
    earned_badge_ids = {row[0] for row in earned_result.all()}

    # Pre-compute stats (lazy — only fetch what we need)
    _hunt_count: Optional[int] = None
    _finds_count: Optional[int] = None

    async def hunt_count() -> int:
        nonlocal _hunt_count
        if _hunt_count is None:
            _hunt_count = await _get_hunt_count(user_id, db)
        return _hunt_count

    async def finds_count() -> int:
        nonlocal _finds_count
        if _finds_count is None:
            _finds_count = await _get_finds_count(user_id, db)
        return _finds_count

    newly_earned: List[Badge] = []

    for badge in all_badges:
        if badge.id in earned_badge_ids:
            continue

        criteria = badge.criteria or {}
        criteria_type = criteria.get("type")
        threshold = criteria.get("threshold", 0)

        earned = False

        if criteria_type == "hunt_count":
            earned = (await hunt_count()) >= threshold
        elif criteria_type == "finds_count":
            earned = (await finds_count()) >= threshold
        # site_type and score_threshold are not auto-evaluated yet

        if earned:
            user_badge = UserBadge(
                id=uuid.uuid4(),
                user_id=user_id,
                badge_id=badge.id,
            )
            db.add(user_badge)
            newly_earned.append(badge)

    if newly_earned:
        await db.flush()

    return newly_earned


async def get_badge_progress(
    user_id: uuid.UUID, db: AsyncSession
) -> list[dict]:
    """
    Return progress information for every badge.

    Each dict contains:
      - ``badge``: the Badge ORM object
      - ``earned``: bool
      - ``earned_at``: datetime or None
      - ``current_value``: int or None (progress toward threshold)
      - ``threshold``: int or None
    """
    all_badges_result = await db.execute(select(Badge))
    all_badges: List[Badge] = list(all_badges_result.scalars().all())

    earned_result = await db.execute(
        select(UserBadge).where(UserBadge.user_id == user_id)
    )
    earned_map = {ub.badge_id: ub for ub in earned_result.scalars().all()}

    hunt_count = await _get_hunt_count(user_id, db)
    finds_count = await _get_finds_count(user_id, db)

    progress_list = []
    for badge in all_badges:
        user_badge = earned_map.get(badge.id)
        criteria = badge.criteria or {}
        criteria_type = criteria.get("type")
        threshold = criteria.get("threshold")

        current_value: Optional[int] = None
        if criteria_type == "hunt_count":
            current_value = hunt_count
        elif criteria_type == "finds_count":
            current_value = finds_count

        progress_list.append(
            {
                "badge": badge,
                "earned": user_badge is not None,
                "earned_at": user_badge.earned_at if user_badge else None,
                "current_value": current_value,
                "threshold": threshold,
            }
        )

    return progress_list
