"""
FastAPI authentication dependencies using Supabase JWT.

Validates Bearer tokens issued by Supabase Auth and auto-provisions a local
User row on first login.  Supports both HS256 (shared-secret) and ES256
(elliptic-curve) signed tokens by fetching the JWKS from Supabase's
well-known endpoint on first use and caching it for one hour.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional

import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.database import User, get_db

logger = logging.getLogger(__name__)

_bearer = HTTPBearer(auto_error=False)

# ── JWKS cache ────────────────────────────────────────────────────────────────
_jwks_cache: Optional[Dict[str, Any]] = None
_jwks_fetched_at: float = 0.0
_JWKS_TTL = 3600  # seconds


async def _fetch_jwks(*, force: bool = False) -> Dict[str, Any]:
    """Return the cached JWKS, refreshing from Supabase when stale."""
    global _jwks_cache, _jwks_fetched_at

    now = time.monotonic()
    if not force and _jwks_cache is not None and (now - _jwks_fetched_at) < _JWKS_TTL:
        return _jwks_cache

    jwks_url = (
        f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1/.well-known/jwks.json"
    )
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(jwks_url, timeout=5.0)
            resp.raise_for_status()
            _jwks_cache = resp.json()
            _jwks_fetched_at = now
    except Exception as exc:
        logger.warning("Failed to fetch JWKS from %s: %s", jwks_url, exc)
        if _jwks_cache is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Unable to fetch JWT public keys",
            ) from exc
        # Re-use stale cache on transient network error

    return _jwks_cache  # type: ignore[return-value]


def _find_jwk(
    jwks: Dict[str, Any], kid: Optional[str]
) -> Optional[Dict[str, Any]]:
    """Return the JWK whose kid matches, or the first key when kid is absent."""
    keys = jwks.get("keys", [])
    if kid:
        for key in keys:
            if key.get("kid") == kid:
                return key
    if keys:
        if kid:
            logger.warning("No JWK found for kid=%s; falling back to first key", kid)
        return keys[0]
    return None


async def _decode_token(token: str) -> dict:
    """
    Decode and verify a Supabase JWT.

    Handles both HS256 (shared-secret) and ES256 (JWKS public-key) tokens.
    """
    try:
        header = jwt.get_unverified_header(token)
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    alg = header.get("alg", "HS256")

    if alg == "ES256":
        kid = header.get("kid")
        jwks = await _fetch_jwks()
        jwk_data = _find_jwk(jwks, kid)

        if jwk_data is None:
            # Key might have been rotated — try a forced refresh
            jwks = await _fetch_jwks(force=True)
            jwk_data = _find_jwk(jwks, kid)

        if jwk_data is None:
            logger.warning("No matching JWK found for kid=%s", kid)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
                headers={"WWW-Authenticate": "Bearer"},
            )

        try:
            issuer = (
                f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1"
                if settings.SUPABASE_URL
                else None
            )
            payload = jwt.decode(
                token,
                jwk_data,
                algorithms=["ES256"],
                audience="authenticated",
                issuer=issuer,
            )
        except JWTError as exc:
            logger.debug("ES256 JWT validation failed: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
                headers={"WWW-Authenticate": "Bearer"},
            ) from exc
    else:
        # HS256 fallback for backwards compatibility
        try:
            issuer = (
                f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1"
                if settings.SUPABASE_URL
                else None
            )
            payload = jwt.decode(
                token,
                settings.SUPABASE_JWT_SECRET,
                algorithms=["HS256"],
                audience="authenticated",
                issuer=issuer,
            )
        except JWTError as exc:
            logger.debug("HS256 JWT validation failed: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
                headers={"WWW-Authenticate": "Bearer"},
            ) from exc

    return payload


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Decode the Supabase JWT and return the matching local User row.

    Auto-creates the row on first login.  Raises 401 for missing or invalid
    tokens.  Supports both HS256 and ES256 signed tokens.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    payload = await _decode_token(token)

    supabase_id: str = payload.get("sub", "")
    email: str = payload.get("email", "")

    if not supabase_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing sub claim",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Look up or create the local user row
    result = await db.execute(select(User).where(User.supabase_id == supabase_id))
    user = result.scalar_one_or_none()

    if user is None:
        user = User(supabase_id=supabase_id, email=email)
        db.add(user)
        await db.flush()

    return user


async def optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    """
    Like ``get_current_user`` but returns ``None`` instead of raising 401
    when no token is present.  Useful for endpoints accessible to both
    anonymous visitors and authenticated users.
    """
    if credentials is None:
        return None
    try:
        return await get_current_user(credentials=credentials, db=db)
    except HTTPException:
        return None
