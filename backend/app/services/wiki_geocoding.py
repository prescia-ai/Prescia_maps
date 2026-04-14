"""
Wikipedia Geosearch API — fast coordinate lookup for named Wikipedia articles.

Uses the MediaWiki action API to fetch geographic coordinates embedded in
Wikipedia article geo-templates. Much faster than Nominatim with no rate limit.
Falls back gracefully when an article has no coordinates.

API docs: https://www.mediawiki.org/wiki/API:Coordinates
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Optional, Tuple, Dict

import httpx

logger = logging.getLogger(__name__)

WIKI_API_URL = "https://en.wikipedia.org/w/api.php"
_cache: Dict[str, Optional[Tuple[float, float]]] = {}

# Semaphore to limit concurrent Wikipedia API requests
_sem = asyncio.Semaphore(10)  # Wikipedia allows much higher concurrency than Nominatim

_HEADERS = {
    "User-Agent": "aurik/1.0 (historical research; https://github.com/prescia-ai/Prescia_maps)"
}

# Persistent disk cache path (override via WIKI_GEOCODE_CACHE_PATH env var)
_CACHE_PATH = Path(
    os.environ.get(
        "WIKI_GEOCODE_CACHE_PATH",
        str(Path.home() / ".aurik" / "wiki_geocode_cache.json"),
    )
)


def _load_disk_cache() -> None:
    """Load cached Wikipedia coordinate results from disk into the in-memory cache."""
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
        logger.warning("Failed to save wiki geocode disk cache: %s", exc)


# Populate in-memory cache from disk on module import
_load_disk_cache()


async def get_article_coords(title: str) -> Optional[Tuple[float, float]]:
    """
    Fetch coordinates for a Wikipedia article by its title.

    Uses the Wikipedia API prop=coordinates endpoint. Returns (lat, lon)
    or None if the article has no coordinates or doesn't exist.

    Args:
        title: Wikipedia article title (e.g. "Battle of Gettysburg")

    Returns:
        (latitude, longitude) tuple or None
    """
    if not title or not title.strip():
        return None

    cache_key = title.strip().lower()
    if cache_key in _cache:
        return _cache[cache_key]

    params = {
        "action": "query",
        "prop": "coordinates",
        "titles": title,
        "format": "json",
        "redirects": "1",
    }

    async with _sem:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(WIKI_API_URL, params=params, headers=_HEADERS)
                response.raise_for_status()
                data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.debug("Wikipedia API error for %r: %s", title, exc)
            _cache[cache_key] = None
            return None

    # Parse response — pages dict has page IDs as keys
    pages = data.get("query", {}).get("pages", {})
    for page in pages.values():
        coords_list = page.get("coordinates", [])
        if coords_list:
            coord = coords_list[0]
            try:
                result = (float(coord["lat"]), float(coord["lon"]))
                _cache[cache_key] = result
                _save_disk_cache()
                logger.debug("Wikipedia coords for %r: %s", title, result)
                return result
            except (KeyError, ValueError, TypeError):
                pass

    _cache[cache_key] = None
    _save_disk_cache()
    return None


async def search_and_get_coords(query: str) -> Optional[Tuple[float, float]]:
    """
    Search Wikipedia for the query and get coords from the top result.

    Uses the Wikipedia search API to find the most relevant article,
    then fetches its coordinates. Useful when the exact article title
    is not known (e.g. for scraped place names).

    Args:
        query: Free-text search query (e.g. "Fort Laramie Wyoming")

    Returns:
        (latitude, longitude) tuple or None
    """
    if not query or not query.strip():
        return None

    cache_key = f"search:{query.strip().lower()}"
    if cache_key in _cache:
        return _cache[cache_key]

    # Step 1: search for the article
    search_params = {
        "action": "query",
        "list": "search",
        "srsearch": query,
        "srlimit": 3,
        "format": "json",
    }

    async with _sem:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(WIKI_API_URL, params=search_params, headers=_HEADERS)
                response.raise_for_status()
                data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.debug("Wikipedia search error for %r: %s", query, exc)
            _cache[cache_key] = None
            return None

    results = data.get("query", {}).get("search", [])
    if not results:
        _cache[cache_key] = None
        return None

    # Step 2: try to get coords from top 3 results
    for result in results[:3]:
        title = result.get("title", "")
        if not title:
            continue
        coords = await get_article_coords(title)
        if coords:
            _cache[cache_key] = coords
            _save_disk_cache()
            return coords

    _cache[cache_key] = None
    _save_disk_cache()
    return None


def clear_cache() -> None:
    """Clear the in-memory coordinate cache."""
    _cache.clear()
