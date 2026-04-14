"""
Google OAuth2 helpers for the Google Drive integration.

Provides token encryption/decryption (Fernet) and the core OAuth2
authorization-code flow functions used by the google_auth router.
"""

from __future__ import annotations

import urllib.parse
from typing import TYPE_CHECKING, Optional

import httpx
from cryptography.fernet import Fernet
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings

if TYPE_CHECKING:
    from app.models.database import User

# ---------------------------------------------------------------------------
# Token encryption helpers
# ---------------------------------------------------------------------------

def _get_fernet() -> Fernet:
    """Return a Fernet instance backed by the configured encryption key."""
    key = settings.GOOGLE_TOKEN_ENCRYPTION_KEY
    if not key:
        raise HTTPException(
            status_code=500,
            detail="Google token encryption key is not configured.",
        )
    return Fernet(key.encode())


def encrypt_token(token: str) -> str:
    """Encrypt a plaintext token string using Fernet symmetric encryption.

    Args:
        token: Plaintext OAuth token to encrypt.

    Returns:
        The encrypted token as a UTF-8 string.
    """
    fernet = _get_fernet()
    return fernet.encrypt(token.encode()).decode("utf-8")


def decrypt_token(encrypted: str) -> str:
    """Decrypt a Fernet-encrypted token string back to plaintext.

    Args:
        encrypted: Fernet-encrypted token string.

    Returns:
        The decrypted plaintext token.
    """
    fernet = _get_fernet()
    return fernet.decrypt(encrypted.encode()).decode("utf-8")


# ---------------------------------------------------------------------------
# OAuth flow functions
# ---------------------------------------------------------------------------

_GOOGLE_AUTH_BASE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
_GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"

# Request Drive access plus OpenID Connect scopes so the userinfo endpoint
# returns the user's email after the OAuth callback.
_DRIVE_SCOPE = "openid email https://www.googleapis.com/auth/drive.file"


def build_google_auth_url(state: str) -> str:
    """Build the Google OAuth2 authorization URL.

    Args:
        state: An opaque string (e.g. the user's ID) that Google will echo
               back to the callback so we can identify the user.

    Returns:
        The full Google consent-screen URL that the client should be
        redirected to.
    """
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": _DRIVE_SCOPE,
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }
    return f"{_GOOGLE_AUTH_BASE_URL}?{urllib.parse.urlencode(params)}"


async def exchange_code_for_tokens(code: str) -> dict:
    """Exchange a Google authorization code for access + refresh tokens.

    Args:
        code: The one-time authorization code returned by Google.

    Returns:
        The JSON response dict from Google containing ``access_token``,
        ``refresh_token``, ``expires_in``, ``token_type``, and optionally
        ``scope``.

    Raises:
        HTTPException(400): If Google rejects the token exchange.
    """
    async with httpx.AsyncClient() as client:
        response = await client.post(
            _GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "redirect_uri": settings.GOOGLE_REDIRECT_URI,
                "grant_type": "authorization_code",
            },
        )

    if response.status_code != 200:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to exchange authorization code: {response.text}",
        )

    return response.json()


async def fetch_google_user_email(access_token: str) -> str:
    """Fetch the Google account email address for the authenticated user.

    Args:
        access_token: A valid Google OAuth2 access token.

    Returns:
        The user's Google account email address.

    Raises:
        HTTPException(400): If the userinfo request fails.
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(
            _GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )

    if response.status_code != 200:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to fetch Google user info: {response.text}",
        )

    return response.json()["email"]


# ---------------------------------------------------------------------------
# Token refresh helpers
# ---------------------------------------------------------------------------

async def refresh_access_token(refresh_token: str) -> dict:
    """Exchange a refresh token for a fresh Google access token.

    Args:
        refresh_token: Plaintext Google OAuth2 refresh token.

    Returns:
        JSON response dict containing ``access_token``, ``expires_in``,
        and ``token_type``.

    Raises:
        HTTPException(502): If Google rejects the token exchange.
    """
    async with httpx.AsyncClient() as client:
        response = await client.post(
            _GOOGLE_TOKEN_URL,
            data={
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
        )

    if response.status_code != 200:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to refresh Google access token: {response.text}",
        )

    return response.json()


async def get_valid_access_token(user: User, db: AsyncSession) -> str:
    """Get a fresh Google access token for the given user.

    Decrypts the stored refresh token and exchanges it for a valid access
    token.  If the refresh fails (e.g. user revoked access), the user's
    Google connection fields are cleared and a 401 is raised.

    Args:
        user: The authenticated User ORM instance.
        db:   The active async database session.

    Returns:
        A valid Google OAuth2 access token string.

    Raises:
        HTTPException(400): If the user has not connected Google Drive.
        HTTPException(401): If the refresh token has been revoked.
    """
    if not user.google_refresh_token:
        raise HTTPException(
            status_code=400,
            detail=(
                "Google Drive not connected. "
                "Please connect your Google account in profile settings."
            ),
        )

    plaintext_refresh_token = decrypt_token(user.google_refresh_token)

    try:
        token_data = await refresh_access_token(plaintext_refresh_token)
    except HTTPException:
        # Refresh failed — assume the user revoked access; clear their fields.
        user.google_refresh_token = None
        user.google_connected_at = None
        user.google_email = None
        user.google_folder_id = None
        await db.flush()
        raise HTTPException(
            status_code=401,
            detail=(
                "Google Drive access was revoked. "
                "Please reconnect your Google account in profile settings."
            ),
        )

    return token_data["access_token"]


# ---------------------------------------------------------------------------
# Google Drive folder helper
# ---------------------------------------------------------------------------

_DRIVE_FILES_URL = "https://www.googleapis.com/drive/v3/files"


async def ensure_aurik_folder(
    access_token: str,
    user: Optional[User] = None,
    db: Optional[AsyncSession] = None,
) -> str:
    """Find or create the ``Aurik`` folder in the user's Google Drive.

    If ``user`` and ``db`` are provided, the folder ID is cached on the User
    row so future calls skip the Drive search.  If the cached folder is
    missing or trashed, a fresh search/create is performed and the cache is
    updated.

    Args:
        access_token: A valid Google OAuth2 access token.
        user:         Optional User ORM instance for caching the folder ID.
        db:           Optional async session required when ``user`` is given.

    Returns:
        The Google Drive folder ID for the ``Aurik`` folder.

    Raises:
        HTTPException(502): If any Google Drive API request fails.
    """
    headers = {"Authorization": f"Bearer {access_token}"}

    # ------------------------------------------------------------------
    # 1. If we have a cached folder ID, verify it still exists.
    # ------------------------------------------------------------------
    if user is not None and user.google_folder_id:
        async with httpx.AsyncClient() as client:
            check_resp = await client.get(
                f"{_DRIVE_FILES_URL}/{user.google_folder_id}",
                params={"fields": "id,trashed"},
                headers=headers,
            )
        if check_resp.status_code == 200:
            data = check_resp.json()
            if not data.get("trashed", False):
                return user.google_folder_id
        # Cached ID is gone or trashed — fall through to search/create.
        user.google_folder_id = None

    # ------------------------------------------------------------------
    # 2. Search for an existing "Aurik" folder in Drive root.
    # ------------------------------------------------------------------
    query = (
        "name='Aurik' "
        "and mimeType='application/vnd.google-apps.folder' "
        "and 'root' in parents "
        "and trashed=false"
    )
    async with httpx.AsyncClient() as client:
        search_resp = await client.get(
            _DRIVE_FILES_URL,
            params={"q": query, "fields": "files(id,name)"},
            headers=headers,
        )

    if search_resp.status_code != 200:
        raise HTTPException(
            status_code=502,
            detail="Failed to access Google Drive folder",
        )

    files = search_resp.json().get("files", [])
    if files:
        folder_id = files[0]["id"]
    else:
        # ------------------------------------------------------------------
        # 3. No existing folder found — create it.
        # ------------------------------------------------------------------
        async with httpx.AsyncClient() as client:
            create_resp = await client.post(
                _DRIVE_FILES_URL,
                params={"fields": "id"},
                headers={**headers, "Content-Type": "application/json"},
                json={
                    "name": "Aurik",
                    "mimeType": "application/vnd.google-apps.folder",
                },
            )

        if create_resp.status_code not in (200, 201):
            raise HTTPException(
                status_code=502,
                detail="Failed to access Google Drive folder",
            )

        folder_id = create_resp.json()["id"]

    # ------------------------------------------------------------------
    # 4. Cache the folder ID on the User row if possible.
    # ------------------------------------------------------------------
    if user is not None and db is not None:
        user.google_folder_id = folder_id
        await db.flush()

    return folder_id


# ---------------------------------------------------------------------------
# Shared Drive upload helper
# ---------------------------------------------------------------------------

_DRIVE_UPLOAD_URL = "https://www.googleapis.com/upload/drive/v3/files"
_DRIVE_PERMISSIONS_URL = "https://www.googleapis.com/drive/v3/files/{file_id}/permissions"


async def upload_file_to_drive(
    access_token: str,
    folder_id: str,
    file_name: str,
    file_contents: bytes,
    content_type: str,
) -> str:
    """Upload a file to a specific Google Drive folder and make it publicly readable.

    Returns the Google Drive file ID.
    Raises HTTPException(502) on failure.
    """
    import json as _json

    headers = {"Authorization": f"Bearer {access_token}"}
    metadata = _json.dumps({"name": file_name, "parents": [folder_id]}).encode()
    boundary = "aurik_upload_boundary"
    body = (
        f"--{boundary}\r\n"
        f"Content-Type: application/json; charset=UTF-8\r\n\r\n"
    ).encode() + metadata + (
        f"\r\n--{boundary}\r\n"
        f"Content-Type: {content_type}\r\n\r\n"
    ).encode() + file_contents + f"\r\n--{boundary}--".encode()

    async with httpx.AsyncClient() as client:
        upload_resp = await client.post(
            f"{_DRIVE_UPLOAD_URL}?uploadType=multipart&fields=id",
            headers={
                **headers,
                "Content-Type": f"multipart/related; boundary={boundary}",
            },
            content=body,
            timeout=60.0,
        )

    if upload_resp.status_code not in (200, 201):
        raise HTTPException(status_code=502, detail="Failed to upload file to Google Drive")

    file_id = upload_resp.json().get("id")
    if not file_id:
        raise HTTPException(status_code=502, detail="Failed to upload file to Google Drive")

    async with httpx.AsyncClient() as client:
        perm_resp = await client.post(
            _DRIVE_PERMISSIONS_URL.format(file_id=file_id),
            headers={**headers, "Content-Type": "application/json"},
            json={"role": "reader", "type": "anyone"},
            timeout=30.0,
        )

    if perm_resp.status_code not in (200, 201):
        raise HTTPException(status_code=502, detail="Failed to upload file to Google Drive")

    return file_id
