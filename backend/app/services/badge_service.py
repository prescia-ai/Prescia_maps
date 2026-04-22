"""
Badge service — checks badge criteria and awards new badges to users.

Supports the following criteria types:
  - hunt_count:           number of UserPin records for the user
  - finds_count:          sum of UserPin.finds_count for the user
  - single_hunt_finds:    max UserPin.finds_count in a single hunt
  - grid_search_count:    number of hunts where search_pattern == 'grid'
  - deep_find:            max UserPin.depth_inches across all hunts
  - site_type:            hunts near a Location of the given type (PostGIS)
  - collection_type_count / collection_material_count: collection items
  - approved_submissions: community pin submissions approved by admins

The following criteria types require further implementation:
  - max_distance_traveled / linear_feature_proximity: PostGIS (TODO)
  - score_threshold: future implementation
  - group_hunt_count / group_hunt_led: requires group system (deferred)
"""

from __future__ import annotations

from typing import List
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import Badge, UserBadge, UserPin
from app.services.notification_service import create_notification


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

        elif criteria_type == "collection_type_count" and threshold is not None:
            from app.models.database import CollectionPhoto
            find_type = criteria.get("find_type")
            r = await db.execute(
                select(func.count()).select_from(CollectionPhoto).where(
                    CollectionPhoto.user_id == user_id,
                    CollectionPhoto.find_type == find_type,
                )
            )
            earned = (r.scalar() or 0) >= threshold

        elif criteria_type == "collection_material_count" and threshold is not None:
            from app.models.database import CollectionPhoto
            material = criteria.get("material")
            r = await db.execute(
                select(func.count()).select_from(CollectionPhoto).where(
                    CollectionPhoto.user_id == user_id,
                    CollectionPhoto.material == material,
                )
            )
            earned = (r.scalar() or 0) >= threshold

        elif criteria_type == "single_hunt_finds" and threshold is not None:
            # Check max finds in a single hunt
            r = await db.execute(
                select(func.max(UserPin.finds_count)).where(UserPin.user_id == user_id)
            )
            max_finds = r.scalar() or 0
            earned = max_finds >= threshold

        elif criteria_type == "grid_search_count" and threshold is not None:
            # Count hunts where search_pattern is 'grid'
            r = await db.execute(
                select(func.count()).select_from(UserPin).where(
                    UserPin.user_id == user_id,
                    UserPin.search_pattern == "grid",
                )
            )
            earned = (r.scalar() or 0) >= threshold

        elif criteria_type == "deep_find":
            # Check if any find was recovered from threshold depth or deeper
            threshold_inches = criteria.get("threshold_inches", 12)
            r = await db.execute(
                select(func.max(UserPin.depth_inches)).where(UserPin.user_id == user_id)
            )
            max_depth = r.scalar() or 0
            earned = max_depth >= threshold_inches

        elif criteria_type == "approved_submissions" and threshold is not None:
            from app.models.database import PinSubmission
            r = await db.execute(
                select(func.count()).select_from(PinSubmission).where(
                    PinSubmission.submitter_id == user_id,
                    PinSubmission.status == "approved",
                )
            )
            earned = (r.scalar() or 0) >= threshold

        elif criteria_type in ("max_distance_traveled", "linear_feature_proximity"):
            # TODO: PostGIS implementation
            earned = False

        elif criteria_type == "site_type":
            # Check if user has a hunt near a location of the given site type
            site_type_value = criteria.get("site_type")
            if site_type_value is not None:
                from app.models.database import Location
                min_count = threshold if threshold is not None else 1
                r = await db.execute(
                    select(func.count()).select_from(UserPin).where(
                        UserPin.user_id == user_id,
                        UserPin.geom.isnot(None),
                        select(Location.id).where(
                            Location.type == site_type_value,
                            Location.geom.isnot(None),
                            # 0.01 degrees ≈ ~1 km proximity check (WGS-84 degrees)
                            func.ST_DWithin(UserPin.geom, Location.geom, 0.01),
                        ).correlate(UserPin).exists(),
                    )
                )
                earned = (r.scalar() or 0) >= min_count
            else:
                earned = False

        elif criteria_type == "score_threshold":
            # Future implementation — skip for now
            earned = False

        if earned:
            user_badge = UserBadge(user_id=user_id, badge_id=badge.id)
            db.add(user_badge)
            newly_earned.append(badge)

    if newly_earned:
        await db.flush()
        # Notify the user for each newly earned badge
        for badge in newly_earned:
            await create_notification(
                db,
                type="badge_earned",
                user_id=user_id,
                actor_id=None,
                ref_id=str(badge.id),
            )

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

    # Pre-compute approved submissions count
    from app.models.database import PinSubmission
    approved_submissions_result = await db.execute(
        select(func.count()).select_from(PinSubmission).where(
            PinSubmission.submitter_id == user_id,
            PinSubmission.status == "approved",
        )
    )
    approved_submissions = approved_submissions_result.scalar() or 0

    from app.models.database import CollectionPhoto
    progress_list = []
    for badge in all_badges:
        criteria = badge.criteria or {}
        criteria_type = criteria.get("type", "")
        threshold = criteria.get("threshold")

        if criteria_type == "hunt_count":
            current_value = hunt_count
        elif criteria_type == "finds_count":
            current_value = finds_count
        elif criteria_type == "approved_submissions":
            current_value = approved_submissions
        elif criteria_type == "collection_type_count":
            find_type = criteria.get("find_type")
            r = await db.execute(
                select(func.count()).select_from(CollectionPhoto).where(
                    CollectionPhoto.user_id == user_id,
                    CollectionPhoto.find_type == find_type,
                )
            )
            current_value = r.scalar() or 0
        elif criteria_type == "collection_material_count":
            material = criteria.get("material")
            r = await db.execute(
                select(func.count()).select_from(CollectionPhoto).where(
                    CollectionPhoto.user_id == user_id,
                    CollectionPhoto.material == material,
                )
            )
            current_value = r.scalar() or 0
        elif criteria_type == "single_hunt_finds":
            r = await db.execute(
                select(func.max(UserPin.finds_count)).where(UserPin.user_id == user_id)
            )
            current_value = r.scalar() or 0
        elif criteria_type == "grid_search_count":
            r = await db.execute(
                select(func.count()).select_from(UserPin).where(
                    UserPin.user_id == user_id,
                    UserPin.search_pattern == "grid",
                )
            )
            current_value = r.scalar() or 0
        elif criteria_type == "deep_find":
            r = await db.execute(
                select(func.max(UserPin.depth_inches)).where(UserPin.user_id == user_id)
            )
            current_value = r.scalar() or 0
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
