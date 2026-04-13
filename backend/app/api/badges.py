"""
Badge endpoints — list badges and track user progress.
"""

from __future__ import annotations

import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.models.database import Badge, User, UserBadge, get_db
from app.models.schemas import (
    BadgeCheckResponse,
    BadgeProgressResponse,
    BadgeResponse,
    UserBadgeResponse,
)
from app.services.badge_service import check_all_badges, get_badge_progress

router = APIRouter(prefix="/badges", tags=["badges"])


def _badge_to_response(badge: Badge) -> BadgeResponse:
    return BadgeResponse.from_orm_with_url(badge)


# ---------------------------------------------------------------------------
# Public: list all badges
# ---------------------------------------------------------------------------


@router.get(
    "",
    response_model=List[BadgeResponse],
    summary="List all achievement badges",
)
async def list_badges(db: AsyncSession = Depends(get_db)) -> List[BadgeResponse]:
    """Return all badge definitions ordered by category then name."""
    result = await db.execute(select(Badge).order_by(Badge.category, Badge.name))
    badges = result.scalars().all()
    return [_badge_to_response(b) for b in badges]


# ---------------------------------------------------------------------------
# Authenticated: check and award badges for the current user
# ---------------------------------------------------------------------------


@router.post(
    "/check",
    response_model=BadgeCheckResponse,
    summary="Check and award any newly earned badges",
)
async def check_badges(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> BadgeCheckResponse:
    """Evaluate all badge criteria and award any newly earned badges."""
    newly_earned = await check_all_badges(current_user.id, db)

    total_result = await db.execute(
        select(func.count()).select_from(UserBadge).where(
            UserBadge.user_id == current_user.id
        )
    )
    total = total_result.scalar_one() or 0

    return BadgeCheckResponse(
        newly_earned=[_badge_to_response(b) for b in newly_earned],
        total_earned=total,
    )


# ---------------------------------------------------------------------------
# Authenticated: current user's badge progress
# ---------------------------------------------------------------------------


@router.get(
    "/me/progress",
    response_model=List[BadgeProgressResponse],
    summary="Get current user's progress on all badges",
)
async def my_badge_progress(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[BadgeProgressResponse]:
    """Return progress info for all badges (earned + unearned with progress tracking)."""
    progress = await get_badge_progress(current_user.id, db)
    return [
        BadgeProgressResponse(
            badge=_badge_to_response(item["badge"]),
            earned=item["earned"],
            earned_at=item["earned_at"],
            current_value=item["current_value"],
            threshold=item["threshold"],
        )
        for item in progress
    ]


# ---------------------------------------------------------------------------
# Public: a specific user's earned badges (by username)
# ---------------------------------------------------------------------------


@router.get(
    "/users/{username}",
    response_model=List[BadgeResponse],
    summary="Get badges earned by a user",
)
async def user_badges(
    username: str,
    db: AsyncSession = Depends(get_db),
) -> List[BadgeResponse]:
    """Return all badges earned by the given username."""
    user_result = await db.execute(
        select(User).where(User.username == username)
    )
    user = user_result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    result = await db.execute(
        select(Badge)
        .join(UserBadge, UserBadge.badge_id == Badge.id)
        .where(UserBadge.user_id == user.id)
        .order_by(UserBadge.earned_at.desc())
    )
    badges = result.scalars().all()
    return [_badge_to_response(b) for b in badges]
