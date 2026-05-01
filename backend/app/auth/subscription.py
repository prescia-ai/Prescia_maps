"""
Subscription tier enforcement dependency.

Usage example (apply in a follow-up PR):

    from app.auth.subscription import require_tier

    @router.get("/pro-only-endpoint")
    async def pro_endpoint(user: User = Depends(require_tier("pro"))):
        ...

Endpoints in the following routers will adopt ``require_tier("pro")`` in a
follow-up PR once feature gating is ready:
  - pins.py
  - submissions.py
  - groups.py
  - group_events.py
  - hunt_plans.py
  - routes.py (certain endpoints)
"""

from __future__ import annotations

from fastapi import Depends, HTTPException

from app.auth.deps import get_current_user
from app.models.database import User


def require_tier(min_tier: str):
    """
    FastAPI dependency factory that enforces a minimum subscription tier.

    Parameters
    ----------
    min_tier:
        The minimum required tier.  Currently only ``"pro"`` is meaningful.

    Returns
    -------
    A FastAPI dependency callable that resolves to the authenticated ``User``
    when the tier requirement is satisfied, or raises ``HTTP 402`` otherwise.
    """

    async def _checker(current_user: User = Depends(get_current_user)) -> User:
        if min_tier == "pro" and not current_user.is_pro:
            raise HTTPException(
                status_code=402,
                detail={"error": "subscription_required", "required_tier": "pro"},
            )
        return current_user

    return _checker
