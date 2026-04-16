"""
Notification endpoints.

Routes (all mounted under /api/v1 in main.py):
  GET   /notifications       — return unread count + paginated list (auth required)
  POST  /notifications/read  — mark specified notifications as read (auth required)
"""

from __future__ import annotations

from datetime import datetime
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.models.database import User, get_db
from app.services.notification_service import (
    get_notifications,
    mark_notifications_read,
)

router = APIRouter(prefix="/notifications", tags=["notifications"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class NotificationResponse(BaseModel):
    """A single notification item returned to the client."""

    id: UUID
    type: str
    actor_id: UUID | None
    ref_id: str | None
    read: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class NotificationsListResponse(BaseModel):
    """Paginated notifications response."""

    unread_count: int
    notifications: List[NotificationResponse]


class MarkReadRequest(BaseModel):
    """Request body for marking notifications as read."""

    notification_ids: List[UUID]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get(
    "",
    response_model=NotificationsListResponse,
    summary="Get notifications for the current user",
)
async def list_notifications(
    limit: int = Query(20, ge=1, le=100, description="Maximum number of notifications to return"),
    offset: int = Query(0, ge=0, description="Number of notifications to skip"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NotificationsListResponse:
    """
    Return the authenticated user's unread count and a paginated list of
    notifications, ordered newest first.
    """
    result = await get_notifications(
        db,
        user_id=current_user.id,
        limit=limit,
        offset=offset,
    )
    return NotificationsListResponse(
        unread_count=result["unread_count"],
        notifications=[
            NotificationResponse.model_validate(n) for n in result["notifications"]
        ],
    )


@router.post(
    "/read",
    status_code=204,
    summary="Mark notifications as read",
)
async def mark_read(
    body: MarkReadRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Mark the specified notifications as read for the authenticated user.

    Only notifications belonging to the current user are affected.
    """
    await mark_notifications_read(
        db,
        user_id=current_user.id,
        notification_ids=body.notification_ids,
    )
