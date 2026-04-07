"""
Geocoding service with Wikipedia-first strategy and Nominatim fallback.

Tries the Wikipedia Geosearch API first (fast, no rate limit), then falls
back to Nominatim (1 req/sec) only when Wikipedia returns nothing.
"""

import asyncio
import json
import logging
import os
import time
from pathlib import Path
from typing import Optional, Tuple

import httpx

from app.config import settings
from app.services import wiki_geocoding

logger = logging.getLogger(__name__)

# In-memory cache: query string -> (lat, lon) or None
_cache: dict[str, Optional[Tuple[float, float]]] = {}

# Persistent disk cache path (override via GEOCODE_CACHE_PATH env var)
_CACHE_PATH = Path(
    os.environ.get(
        "GEOCODE_CACHE_PATH",
        str(Path.home() / ".prescia_maps" / "geocode_cache.json"),
    )
)


def _load_disk_cache() -> None:
    """Load cached geocoding results from disk into the in-memory cache."""
    try:
        with open(_CACHE_PATH) as fh:
            data = json.load(fh)
        for key, value in data.items():
            _cache[key] = tuple(value) if value is not None else None  # type: ignore[assignment]
    except Exception:
        pass  # Missing or corrupt cache file — start fresh


def _save_disk_cache() -> None:
    """Atomically write the in-memory cache to disk."""
    try:
        _CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = _CACHE_PATH.with_suffix(".tmp")
        with open(tmp, "w") as fh:
            json.dump(
                {k: list(v) if v is not None else None for k, v in _cache.items()},
                fh,
            )
        os.replace(tmp, _CACHE_PATH)
    except Exception as exc:
        logger.warning("Failed to save geocode disk cache: %s", exc)


# Populate in-memory cache from disk on module import
_load_disk_cache()

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

    Strategy (in order):
    1. Wikipedia article coordinates (fast, no rate limit)
    2. Wikipedia search + article coordinates (for non-exact titles)
    3. Nominatim free-text geocoding (slow fallback, 1 req/sec)

    Results are cached in memory.

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

    # Strategy 1: Direct Wikipedia article lookup
    coords = await wiki_geocoding.get_article_coords(query)
    if coords:
        _cache[cache_key] = coords
        _save_disk_cache()
        return coords

    # Strategy 2: Wikipedia search
    coords = await wiki_geocoding.search_and_get_coords(query)
    if coords:
        _cache[cache_key] = coords
        _save_disk_cache()
        return coords

    # Strategy 3: Nominatim fallback (rate-limited)
    logger.debug("Falling back to Nominatim for %r", query)
    result = await _rate_limited_get({"q": query})
    if result:
        try:
            coords = (float(result["lat"]), float(result["lon"]))
            _cache[cache_key] = coords
            _save_disk_cache()
            logger.debug("Nominatim geocoded %r -> %s", query, coords)
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
            _save_disk_cache()
            return coords
        except (KeyError, ValueError):
            pass

    _cache[cache_key] = None
    return None


def clear_cache() -> None:
    """Clear the in-memory geocoding cache (useful for testing)."""
    _cache.clear()
