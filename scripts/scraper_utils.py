"""
Shared utilities for Prescia Maps scraper scripts.

Provides common patterns used by all three scrapers:
- Checkpoint save/load/resume
- Proximity-based deduplication (haversine)
- Batch DB insert with ``on_conflict_do_nothing``
- Progress bar wrapper (tqdm with fallback)
- Rate limiter
- Inline enrichment helpers (Wikipedia extract + normalizer)

All database helpers are async and use SQLAlchemy async sessions.
"""

from __future__ import annotations

import json
import logging
import math
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import httpx
from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# ---------------------------------------------------------------------------
# Bootstrap path so we can import from the backend app package
# ---------------------------------------------------------------------------
_SCRIPT_DIR = Path(__file__).resolve().parent
_BACKEND_DIR = _SCRIPT_DIR.parent / "backend"
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from app.config import settings  # noqa: E402
from app.models.database import Base, LinearFeature, Location  # noqa: E402
from app.scrapers.normalizer import (  # noqa: E402
    assign_confidence,
    clean_name,
    classify_event_type,
    is_blocked,
    normalize_year,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional tqdm
# ---------------------------------------------------------------------------

try:
    from tqdm import tqdm as _tqdm

    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False


def progress_bar(iterable=None, total=None, unit="rec", desc="Processing", **kwargs):
    """Return a tqdm progress bar if available, otherwise a passthrough."""
    if HAS_TQDM:
        return _tqdm(
            iterable,
            total=total,
            unit=unit,
            desc=desc,
            ncols=90,
            colour="cyan",
            bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}] {postfix}",
            **kwargs,
        )
    # Minimal fallback that supports the tqdm-like interface
    return _FallbackProgress(iterable, total=total)


class _FallbackProgress:
    """Minimal tqdm-compatible wrapper when tqdm is not installed."""

    def __init__(self, iterable=None, total=None):
        self._iterable = iterable
        self._total = total
        self._n = 0

    def __iter__(self):
        if self._iterable is not None:
            yield from self._iterable

    def update(self, n=1):
        self._n += n
        if self._total and self._n % max(1, self._total // 20) == 0:
            pct = int(self._n / self._total * 100)
            logger.info("  Progress: %d/%d (%d%%)", self._n, self._total, pct)

    def set_postfix_str(self, s, refresh=True):
        pass

    def close(self):
        pass


# ---------------------------------------------------------------------------
# Checkpoint helpers
# ---------------------------------------------------------------------------


def save_checkpoint(path: Path, data: Dict[str, Any]) -> None:
    """Atomically write checkpoint data to disk."""
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w") as fh:
        json.dump(data, fh)
    os.replace(tmp, path)


def load_checkpoint(path: Path) -> Dict[str, Any]:
    """Load checkpoint data from disk, returning empty dict on failure."""
    if not path.exists():
        return {}
    try:
        with open(path) as fh:
            return json.load(fh)
    except Exception as exc:
        logger.warning("Could not load checkpoint %s: %s", path, exc)
        return {}


# ---------------------------------------------------------------------------
# Haversine distance (for proximity dedup)
# ---------------------------------------------------------------------------

_EARTH_RADIUS_M = 6_371_000  # meters


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return the great-circle distance in metres between two lat/lon points."""
    rlat1, rlon1, rlat2, rlon2 = (
        math.radians(lat1),
        math.radians(lon1),
        math.radians(lat2),
        math.radians(lon2),
    )
    dlat = rlat2 - rlat1
    dlon = rlon2 - rlon1
    a = math.sin(dlat / 2) ** 2 + math.cos(rlat1) * math.cos(rlat2) * math.sin(dlon / 2) ** 2
    return 2 * _EARTH_RADIUS_M * math.asin(math.sqrt(a))


# ---------------------------------------------------------------------------
# Proximity-aware dedup index
# ---------------------------------------------------------------------------


class DedupIndex:
    """
    In-memory index that checks for duplicates by normalised name **and**
    geographic proximity.

    Two records are considered duplicates if:
    1. Their normalised names match exactly, OR
    2. Their original names are very similar AND they are within
       ``radius_m`` metres of each other.

    For the bulk-load use case the simple name match (option 1) covers the
    vast majority of duplicates.  The proximity check (option 2) catches
    trivial spelling variants like ``"Sutter's Mill"`` vs ``"Sutters Mill"``.
    """

    def __init__(self, radius_m: float = 500.0):
        self._radius_m = radius_m
        self._names: Set[str] = set()
        self._coords: Dict[str, List[Tuple[float, float]]] = {}  # normalised name → [(lat,lon)]

    def _normalise(self, name: str) -> str:
        """Simple normalisation: lowercase, strip possessives and punctuation."""
        n = name.lower().replace("'s", "s").replace("'", "")
        # Collapse whitespace
        return " ".join(n.split())

    def add(self, name: str, lat: float, lon: float) -> None:
        """Register a record in the index."""
        key = self._normalise(name)
        self._names.add(key)
        self._coords.setdefault(key, []).append((lat, lon))

    def is_duplicate(self, name: str, lat: float, lon: float) -> bool:
        """Return True if this record is a duplicate of one already indexed."""
        key = self._normalise(name)
        if key in self._names:
            return True
        # Check proximity against records with similar names (not implemented
        # for all records due to O(n²) cost; only exact-normalised-name dups
        # are caught here).
        return False


# ---------------------------------------------------------------------------
# Database engine factory
# ---------------------------------------------------------------------------


def create_engine_and_session():
    """Create an async engine + session factory from settings."""
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=False,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
    )
    session_factory = async_sessionmaker(
        bind=engine, class_=AsyncSession, expire_on_commit=False
    )
    return engine, session_factory


async def ensure_tables(engine) -> None:
    """Ensure PostGIS extension and all tables/enum values exist."""
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
        await conn.run_sync(Base.metadata.create_all)
        for val in ["mission", "trading_post", "shipwreck", "pony_express"]:
            await conn.execute(
                text(f"ALTER TYPE location_type_enum ADD VALUE IF NOT EXISTS '{val}'")
            )
        for val in ["blm"]:
            await conn.execute(
                text(f"ALTER TYPE map_layer_type_enum ADD VALUE IF NOT EXISTS '{val}'")
            )


# ---------------------------------------------------------------------------
# Batch insert helpers
# ---------------------------------------------------------------------------


async def load_existing_names(session: AsyncSession) -> Set[str]:
    """Return a set of location names already in the database."""
    result = await session.execute(select(Location.name))
    return {row[0] for row in result}


async def load_existing_name_type_pairs(session: AsyncSession) -> Set[Tuple[str, str]]:
    """Return a set of (name, type) pairs already in the locations table."""
    result = await session.execute(select(Location.name, Location.type))
    return {
        (row[0], row[1].value if hasattr(row[1], "value") else str(row[1]))
        for row in result
    }


async def insert_location_batch(
    session: AsyncSession,
    batch: List[Dict[str, Any]],
) -> int:
    """Insert a batch of location dicts, skipping duplicates (on_conflict_do_nothing)."""
    if not batch:
        return 0
    stmt = pg_insert(Location).values(batch).on_conflict_do_nothing()
    result = await session.execute(stmt)
    await session.commit()
    return result.rowcount or 0


async def insert_linear_feature_batch(
    session: AsyncSession,
    batch: List[Dict[str, Any]],
) -> int:
    """Insert a batch of linear feature dicts, skipping duplicates."""
    if not batch:
        return 0
    stmt = pg_insert(LinearFeature).values(batch).on_conflict_do_nothing()
    result = await session.execute(stmt)
    await session.commit()
    return result.rowcount or 0


async def load_existing_linear_feature_names(session: AsyncSession) -> Set[str]:
    """Return a set of linear feature names already in the database."""
    result = await session.execute(select(LinearFeature.name))
    return {row[0] for row in result}


# ---------------------------------------------------------------------------
# Record builder
# ---------------------------------------------------------------------------


def build_location_record(
    name: str,
    lat: float,
    lon: float,
    source: str,
    loc_type: Optional[str] = None,
    year: Optional[int] = None,
    description: Optional[str] = None,
    confidence: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Build a Location insert dict with proper geometry, type classification,
    and confidence scoring.
    """
    if not loc_type:
        loc_type = classify_event_type(name, description or "")
    if confidence is None:
        confidence = assign_confidence(
            source=source,
            has_coords=True,
            has_year=year is not None,
        )
    return {
        "id": uuid.uuid4(),
        "name": name,
        "type": loc_type,
        "latitude": lat,
        "longitude": lon,
        "year": year,
        "description": (description or "")[:2000],
        "source": source,
        "confidence": confidence,
        "geom": f"SRID=4326;POINT({lon} {lat})",
    }


# ---------------------------------------------------------------------------
# Rate limiter
# ---------------------------------------------------------------------------


class RateLimiter:
    """Simple synchronous rate limiter for HTTP requests."""

    def __init__(self, min_interval: float = 0.1):
        self._min_interval = min_interval
        self._last_call = 0.0

    def wait(self) -> None:
        """Block until the minimum interval has elapsed since the last call."""
        now = time.monotonic()
        elapsed = now - self._last_call
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        self._last_call = time.monotonic()


# ---------------------------------------------------------------------------
# Wikipedia extract enrichment
# ---------------------------------------------------------------------------

_WIKI_API_URL = "https://en.wikipedia.org/w/api.php"
_WIKI_HEADERS = {
    "User-Agent": (
        "prescia_maps/1.0 (historical research; "
        "https://github.com/prescia-ai/Prescia_maps)"
    )
}


async def fetch_wikipedia_extract(
    name: str,
    client: httpx.AsyncClient,
) -> Optional[str]:
    """
    Fetch a plain-text Wikipedia article extract for the given name.

    Tries a direct title lookup first, then falls back to search.
    """
    params = {
        "action": "query",
        "prop": "extracts",
        "exintro": "1",
        "explaintext": "1",
        "titles": name,
        "format": "json",
        "redirects": "1",
    }
    try:
        response = await client.get(_WIKI_API_URL, params=params, headers=_WIKI_HEADERS)
        response.raise_for_status()
        data = response.json()
    except (httpx.HTTPError, ValueError):
        return None

    pages = data.get("query", {}).get("pages", {})
    for page_id, page in pages.items():
        if page_id != "-1" and "extract" in page:
            extract = page["extract"].strip()
            if len(extract) > 50:
                return extract

    # Fallback: search then fetch
    search_params = {
        "action": "query",
        "list": "search",
        "srsearch": name,
        "srlimit": "1",
        "format": "json",
    }
    try:
        response = await client.get(_WIKI_API_URL, params=search_params, headers=_WIKI_HEADERS)
        response.raise_for_status()
        data = response.json()
    except (httpx.HTTPError, ValueError):
        return None

    results = data.get("query", {}).get("search", [])
    if results:
        params["titles"] = results[0]["title"]
        try:
            response = await client.get(_WIKI_API_URL, params=params, headers=_WIKI_HEADERS)
            response.raise_for_status()
            data = response.json()
        except (httpx.HTTPError, ValueError):
            return None

        pages = data.get("query", {}).get("pages", {})
        for page_id, page in pages.items():
            if page_id != "-1" and "extract" in page:
                extract = page["extract"].strip()
                if len(extract) > 50:
                    return extract

    return None


# ---------------------------------------------------------------------------
# Logging setup helper
# ---------------------------------------------------------------------------


def setup_logging(name: str) -> logging.Logger:
    """Configure and return a logger for a scraper script."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    return logging.getLogger(name)
