"""
Google OAuth2 helpers for the Google Drive integration.

Provides token encryption/decryption (Fernet) and the core OAuth2
authorization-code flow functions used by the google_auth router.
"""

from __future__ import annotations

import urllib.parse

import httpx
from cryptography.fernet import Fernet
from fastapi import HTTPException

from app.config import settings

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

# Only request access to files created by our app — not the user's entire Drive.
_DRIVE_SCOPE = "https://www.googleapis.com/auth/drive.file"


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
