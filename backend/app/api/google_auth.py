"""
Google OAuth2 API endpoints.

GET /google/auth-url  — Returns the Google consent URL (requires JWT auth).
GET /google/callback  — OAuth2 callback (browser redirect from Google, no JWT).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.auth.google import (
    build_google_auth_url,
    encrypt_token,
    ensure_prescia_folder,
    exchange_code_for_tokens,
    fetch_google_user_email,
    get_valid_access_token,
)
from app.config import settings
from app.models.database import User, get_db

router = APIRouter(prefix="/google", tags=["google"])


@router.get("/auth-url")
async def get_google_auth_url(
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    """Return the Google OAuth2 consent-screen URL for the current user.

    The user's ID is encoded in the ``state`` parameter so the callback
    can identify which user is connecting their Google account.
    """
    state = str(current_user.id)
    url = build_google_auth_url(state)
    return {"url": url}


@router.get("/callback")
async def google_oauth_callback(
    code: str = Query(...),
    state: str = Query(...),
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    """Handle the Google OAuth2 callback after the user grants consent.

    This endpoint is not protected by JWT — it is a browser redirect from
    Google's consent screen.  The ``state`` parameter carries the user's ID
    so we can look them up in the database.

    On success:  redirects to ``{FRONTEND_URL}/profile/settings?google=connected``
    On failure:  redirects to ``{FRONTEND_URL}/profile/settings?google=error``
    """
    error_redirect = RedirectResponse(
        url=f"{settings.FRONTEND_URL}/profile/settings?google=error",
        status_code=302,
    )
    success_redirect = RedirectResponse(
        url=f"{settings.FRONTEND_URL}/profile/settings?google=connected",
        status_code=302,
    )

    # ------------------------------------------------------------------
    # 1. Look up the user identified by the state parameter.
    # ------------------------------------------------------------------
    try:
        user_id = uuid.UUID(state)
    except (ValueError, AttributeError):
        return error_redirect

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        return error_redirect

    # ------------------------------------------------------------------
    # 2. Exchange the authorization code for tokens.
    # ------------------------------------------------------------------
    try:
        token_data = await exchange_code_for_tokens(code)
    except HTTPException:
        return error_redirect

    access_token: str | None = token_data.get("access_token")
    refresh_token: str | None = token_data.get("refresh_token")

    if not access_token:
        return error_redirect

    # ------------------------------------------------------------------
    # 3. Fetch the connected Google account email.
    # ------------------------------------------------------------------
    try:
        google_email = await fetch_google_user_email(access_token)
    except HTTPException:
        return error_redirect

    # ------------------------------------------------------------------
    # 4. Persist the tokens and metadata on the User row.
    #    If no refresh_token was returned (happens on re-auth without
    #    prompt=consent), keep the existing one.
    # ------------------------------------------------------------------
    try:
        if refresh_token:
            user.google_refresh_token = encrypt_token(refresh_token)
        user.google_connected_at = datetime.now(timezone.utc)
        user.google_email = google_email
        await db.commit()
    except Exception:
        await db.rollback()
        return error_redirect

    return success_redirect


@router.get("/status")
async def google_drive_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return the Google Drive connection status for the current user.

    If connected, also verifies the token is still valid and ensures the
    Prescia Maps folder exists.
    """
    if not current_user.google_refresh_token:
        return {
            "connected": False,
            "google_email": None,
            "connected_at": None,
            "has_folder": False,
        }

    # Try to get a valid access token and verify the folder exists.
    has_folder = False
    try:
        access_token = await get_valid_access_token(current_user, db)
        await ensure_prescia_folder(access_token, user=current_user, db=db)
        has_folder = True
    except HTTPException:
        # Token revoked or Drive unavailable — has_folder stays False.
        # get_valid_access_token clears Google fields on revocation.
        pass

    # After get_valid_access_token, the user may have been disconnected
    # (fields cleared) if the refresh token was revoked.
    if not current_user.google_refresh_token:
        return {
            "connected": False,
            "google_email": None,
            "connected_at": None,
            "has_folder": False,
        }

    connected_at = current_user.google_connected_at
    return {
        "connected": True,
        "google_email": current_user.google_email,
        "connected_at": connected_at.isoformat() if connected_at else None,
        "has_folder": has_folder,
    }


@router.post("/disconnect")
async def google_drive_disconnect(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Disconnect Google Drive for the current user.

    Clears all Google-related fields on the User row.
    """
    current_user.google_refresh_token = None
    current_user.google_connected_at = None
    current_user.google_email = None
    current_user.google_folder_id = None
    await db.flush()
    return {"status": "disconnected"}
