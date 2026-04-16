"""
Notification service — creates and retrieves in-app notifications.

Functions:
  create_notification   — insert a new Notification row
  get_notifications     — return unread count + paginated list for a user
  mark_notifications_read — mark specified notifications as read
"""

from __future__ import annotations

from typing import List
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import Notification


async def create_notification(
    db: AsyncSession,
    *,
    type: str,
    user_id: UUID,
    actor_id: UUID | None = None,
    ref_id: str | None = None,
) -> Notification:
    """
    Insert a new Notification row and return the persisted object.

    Args:
        db:       Async database session.
        type:     Event type string (e.g. "like", "comment", "badge_earned").
        user_id:  Recipient user ID.
        actor_id: User who triggered the event; ``None`` for system events.
        ref_id:   Generic reference ID (post UUID, badge UUID, group UUID …).
    """
    notification = Notification(
        type=type,
        user_id=user_id,
        actor_id=actor_id,
        ref_id=ref_id,
    )
    db.add(notification)
    await db.flush()
    return notification


async def get_notifications(
    db: AsyncSession,
    *,
    user_id: UUID,
    limit: int = 20,
    offset: int = 0,
) -> dict:
    """
    Return the unread count and a paginated list of notifications for a user.

    Notifications are ordered by ``created_at`` descending (newest first).

    Returns a dict with keys:
      - ``unread_count``: total number of unread notifications
      - ``notifications``: list of Notification ORM objects for the page
    """
    # Unread count
    unread_result = await db.execute(
        select(func.count())
        .select_from(Notification)
        .where(Notification.user_id == user_id, Notification.read.is_(False))
    )
    unread_count: int = unread_result.scalar() or 0

    # Paginated list ordered by newest first
    list_result = await db.execute(
        select(Notification)
        .where(Notification.user_id == user_id)
        .order_by(Notification.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    notifications: List[Notification] = list(list_result.scalars().all())

    return {"unread_count": unread_count, "notifications": notifications}


async def mark_notifications_read(
    db: AsyncSession,
    *,
    user_id: UUID,
    notification_ids: List[UUID],
) -> None:
    """
    Mark the specified notifications as read for a given user.

    Only updates notifications that belong to *user_id* to prevent users
    from marking other users' notifications as read.

    Args:
        db:               Async database session.
        user_id:          The authenticated user's ID.
        notification_ids: List of notification UUIDs to mark as read.
    """
    if not notification_ids:
        return

    await db.execute(
        update(Notification)
        .where(
            Notification.user_id == user_id,
            Notification.id.in_(notification_ids),
        )
        .values(read=True)
    )
