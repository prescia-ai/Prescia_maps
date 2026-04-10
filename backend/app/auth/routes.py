"""
Auth API routes — /auth prefix is added in main.py.

Endpoints:
  GET  /auth/me                  — return current user profile
  GET  /auth/profile/{username}  — public profile lookup (no auth required)
  PUT  /auth/profile-setup       — first-time username setup
  PUT  /auth/profile             — update editable profile fields
"""

from __future__ import annotations

import re
from typing import Union

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user, optional_user
from app.models.database import User, UserFollow, get_db
from app.models.schemas import (
    UserProfile,
    UserProfileLimited,
    UserProfilePublic,
    UserProfileSetup,
    UserProfileUpdate,
)

router = APIRouter(prefix="/auth", tags=["auth"])

_USERNAME_RE = re.compile(r"^[a-zA-Z0-9_]{3,30}$")


@router.get("/me", response_model=UserProfile, summary="Get current user profile")
async def get_me(current_user: User = Depends(get_current_user)) -> User:
    """Return the authenticated user's profile."""
    return current_user


@router.get(
    "/profile/{username}",
    summary="Get public profile by username",
)
async def get_public_profile(
    username: str,
    current_user: User | None = Depends(optional_user),
    db: AsyncSession = Depends(get_db),
) -> Union[UserProfilePublic, UserProfileLimited]:
    """
    Return a public profile for *username*.

    If the user's privacy is set to "private", only limited fields are returned.
    No authentication is required, but if the viewer is authenticated
    their ``is_following`` status and follow counts are included.
    """
    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if user.privacy == "private":
        return UserProfileLimited.model_validate(user)

    # Compute follower / following counts
    followers_count_result = await db.execute(
        select(func.count()).select_from(UserFollow).where(UserFollow.following_id == user.id)
    )
    followers_count = followers_count_result.scalar_one()

    following_count_result = await db.execute(
        select(func.count()).select_from(UserFollow).where(UserFollow.follower_id == user.id)
    )
    following_count = following_count_result.scalar_one()

    # Determine if the current viewer is following this user
    is_following = False
    if current_user is not None and current_user.id != user.id:
        follow_result = await db.execute(
            select(UserFollow).where(
                UserFollow.follower_id == current_user.id,
                UserFollow.following_id == user.id,
            )
        )
        is_following = follow_result.scalar_one_or_none() is not None

    return UserProfilePublic(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        bio=user.bio,
        location=user.location,
        privacy=user.privacy,
        created_at=user.created_at,
        followers_count=followers_count,
        following_count=following_count,
        is_following=is_following,
        avatar_url=user.avatar_url,
    )


@router.put(
    "/profile-setup",
    response_model=UserProfile,
    summary="First-time profile setup (set username)",
)
async def profile_setup(
    payload: UserProfileSetup,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Set the username for a user who has not yet completed profile setup.

    Returns 409 if the username is already taken.
    Returns 400 if the user already has a username.
    """
    if current_user.username is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already set",
        )

    # Check uniqueness
    result = await db.execute(
        select(User).where(User.username == payload.username)
    )
    if result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already taken",
        )

    current_user.username = payload.username
    if payload.display_name is not None:
        current_user.display_name = payload.display_name
    if payload.bio is not None:
        current_user.bio = payload.bio
    if payload.location is not None:
        current_user.location = payload.location

    await db.flush()
    return current_user


@router.put("/profile", response_model=UserProfile, summary="Update profile fields")
async def update_profile(
    payload: UserProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Update display_name, bio, location, and/or privacy for the current user."""
    if payload.display_name is not None:
        current_user.display_name = payload.display_name
    if payload.bio is not None:
        current_user.bio = payload.bio
    if payload.location is not None:
        current_user.location = payload.location
    if payload.privacy is not None:
        current_user.privacy = payload.privacy

    await db.flush()
    return current_user
