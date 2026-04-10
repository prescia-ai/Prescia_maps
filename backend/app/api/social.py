"""
Social endpoints — follow / unfollow users and list followers/following.

Routes (all mounted under /api/v1 in main.py):
  POST   /users/{username}/follow     — follow a user
  DELETE /users/{username}/follow     — unfollow a user
  GET    /users/{username}/followers  — list a user's followers
  GET    /users/{username}/following  — list users that a user follows
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.models.database import User, UserFollow, get_db
from app.models.schemas import FollowInfo, FollowListResponse

router = APIRouter(tags=["social"])


async def _get_user_by_username(username: str, db: AsyncSession) -> User:
    """Look up a user by username or raise 404."""
    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


# ---------------------------------------------------------------------------
# POST /users/{username}/follow — follow a user
# ---------------------------------------------------------------------------

@router.post(
    "/users/{username}/follow",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Follow a user",
)
async def follow_user(
    username: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Follow the user identified by *username*."""
    target = await _get_user_by_username(username, db)

    if target.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot follow yourself",
        )

    existing = await db.execute(
        select(UserFollow).where(
            UserFollow.follower_id == current_user.id,
            UserFollow.following_id == target.id,
        )
    )
    if existing.scalar_one_or_none() is not None:
        # Already following — idempotent
        return

    follow = UserFollow(follower_id=current_user.id, following_id=target.id)
    db.add(follow)
    await db.flush()


# ---------------------------------------------------------------------------
# DELETE /users/{username}/follow — unfollow a user
# ---------------------------------------------------------------------------

@router.delete(
    "/users/{username}/follow",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Unfollow a user",
)
async def unfollow_user(
    username: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Unfollow the user identified by *username*."""
    target = await _get_user_by_username(username, db)

    result = await db.execute(
        select(UserFollow).where(
            UserFollow.follower_id == current_user.id,
            UserFollow.following_id == target.id,
        )
    )
    follow = result.scalar_one_or_none()
    if follow is None:
        return  # Not following — idempotent

    await db.delete(follow)
    await db.flush()


# ---------------------------------------------------------------------------
# GET /users/{username}/followers — list followers
# ---------------------------------------------------------------------------

@router.get(
    "/users/{username}/followers",
    response_model=FollowListResponse,
    summary="List a user's followers",
)
async def list_followers(
    username: str,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> FollowListResponse:
    """Return users who follow *username*."""
    target = await _get_user_by_username(username, db)

    total_result = await db.execute(
        select(func.count()).select_from(UserFollow).where(UserFollow.following_id == target.id)
    )
    total = total_result.scalar_one()

    rows = await db.execute(
        select(UserFollow.follower_id)
        .where(UserFollow.following_id == target.id)
        .order_by(UserFollow.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    follower_ids = [r for r in rows.scalars().all()]

    users_result = await db.execute(select(User).where(User.id.in_(follower_ids)))
    users_map = {u.id: u for u in users_result.scalars().all()}

    follow_infos = [
        FollowInfo(
            user_id=uid,
            username=users_map[uid].username if uid in users_map else None,
            display_name=users_map[uid].display_name if uid in users_map else None,
            avatar_url=users_map[uid].avatar_url if uid in users_map else None,
        )
        for uid in follower_ids
    ]
    return FollowListResponse(users=follow_infos, total=total)


# ---------------------------------------------------------------------------
# GET /users/{username}/following — list users that *username* follows
# ---------------------------------------------------------------------------

@router.get(
    "/users/{username}/following",
    response_model=FollowListResponse,
    summary="List users that a user follows",
)
async def list_following(
    username: str,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> FollowListResponse:
    """Return users that *username* is following."""
    target = await _get_user_by_username(username, db)

    total_result = await db.execute(
        select(func.count()).select_from(UserFollow).where(UserFollow.follower_id == target.id)
    )
    total = total_result.scalar_one()

    rows = await db.execute(
        select(UserFollow.following_id)
        .where(UserFollow.follower_id == target.id)
        .order_by(UserFollow.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    following_ids = [r for r in rows.scalars().all()]

    users_result = await db.execute(select(User).where(User.id.in_(following_ids)))
    users_map = {u.id: u for u in users_result.scalars().all()}

    follow_infos = [
        FollowInfo(
            user_id=uid,
            username=users_map[uid].username if uid in users_map else None,
            display_name=users_map[uid].display_name if uid in users_map else None,
            avatar_url=users_map[uid].avatar_url if uid in users_map else None,
        )
        for uid in following_ids
    ]
    return FollowListResponse(users=follow_infos, total=total)
