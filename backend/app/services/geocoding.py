"""
Nominatim geocoding service with rate-limiting and in-memory caching.

Uses geopy's async Nominatim adapter wrapped in a simple asyncio-safe
token-bucket style rate limiter so we stay within the 1 req/sec policy
of the public Nominatim endpoint.
"""

import asyncio
import logging
import time
from functools import lru_cache
from typing import Optional, Tuple

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

# In-memory cache: query string -> (lat, lon) or None
_cache: dict[str, Optional[Tuple[float, float]]] = {}

# Timestamp of the last request (used for rate limiting)
_last_request_time: float = 0.0
_rate_lock = asyncio.Lock()

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"


async def _rate_limited_get(params: dict) -> Optional[dict]:
    """
    Issue a GET request to Nominatim, enforcing the 1 req/sec rate limit.

    Args:
        params: Query parameters forwarded to the Nominatim search endpoint.

    Returns:
        First result dict from the JSON response, or ``None`` if the
        response is empty or an error occurs.
    """
    global _last_request_time

    async with _rate_lock:
        elapsed = time.monotonic() - _last_request_time
        wait = settings.GEOCODING_RATE_LIMIT - elapsed
        if wait > 0:
            await asyncio.sleep(wait)
        _last_request_time = time.monotonic()

    headers = {"User-Agent": settings.GEOCODING_USER_AGENT}
    params = {**params, "format": "json", "limit": 1}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(NOMINATIM_URL, params=params, headers=headers)
            response.raise_for_status()
            results = response.json()
            return results[0] if results else None
    except httpx.HTTPError as exc:
        logger.warning("Nominatim request failed: %s", exc)
        return None
    except (IndexError, ValueError) as exc:
        logger.warning("Nominatim response parse error: %s", exc)
        return None


async def geocode(query: str) -> Optional[Tuple[float, float]]:
    """
    Geocode a free-form place name to (latitude, longitude).

    Results are cached in memory for the lifetime of the process so that
    repeated lookups for the same place don't consume additional API quota.

    Args:
        query: Human-readable location string (e.g. ``"Gettysburg, Pennsylvania"``).

    Returns:
        ``(latitude, longitude)`` tuple if found, ``None`` otherwise.
    """
    if not query or not query.strip():
        return None

    cache_key = query.strip().lower()
    if cache_key in _cache:
        return _cache[cache_key]

    result = await _rate_limited_get({"q": query})
    if result:
        try:
            coords: Tuple[float, float] = (float(result["lat"]), float(result["lon"]))
            _cache[cache_key] = coords
            logger.debug("Geocoded %r -> %s", query, coords)
            return coords
        except (KeyError, ValueError) as exc:
            logger.warning("Could not parse Nominatim result for %r: %s", query, exc)

    _cache[cache_key] = None
    return None


async def geocode_structured(
    city: Optional[str] = None,
    state: Optional[str] = None,
    country: str = "United States",
) -> Optional[Tuple[float, float]]:
    """
    Geocode using structured address components for higher accuracy.

    Args:
        city:    City or locality name.
        state:   State or region name.
        country: Country name (defaults to ``"United States"``).

    Returns:
        ``(latitude, longitude)`` tuple if found, ``None`` otherwise.
    """
    params: dict[str, str] = {"countrycodes": "us"}
    if city:
        params["city"] = city
    if state:
        params["state"] = state

    cache_key = f"{city}|{state}|{country}".lower()
    if cache_key in _cache:
        return _cache[cache_key]

    result = await _rate_limited_get(params)
    if result:
        try:
            coords = (float(result["lat"]), float(result["lon"]))
            _cache[cache_key] = coords
            return coords
        except (KeyError, ValueError):
            pass

    _cache[cache_key] = None
    return None


def clear_cache() -> None:
    """Clear the in-memory geocoding cache (useful for testing)."""
    _cache.clear()
