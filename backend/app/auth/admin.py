"""
Admin-only FastAPI dependency.

Extends ``get_current_user`` to enforce that the authenticated user has the
``is_admin`` flag set.  Returns 403 Forbidden for non-admin users.
"""

from __future__ import annotations

from fastapi import Depends, HTTPException, status

from app.auth.deps import get_current_user
from app.models.database import User


async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """
    Dependency that requires the current user to be an admin.

    Raises:
        HTTPException: 403 if the user does not have ``is_admin = True``.
    """
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current_user
