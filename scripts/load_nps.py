"""
National Park Service API scraper.

Fetches historic battlefield, monument, and historic site records from the
NPS developer API and imports them into the Prescia Maps database.

Usage::

    # Requires NPS_API_KEY to be set in backend/.env (or environment)
    python scripts/load_nps.py

    # Dry-run: print records without inserting
    python scripts/load_nps.py --dry-run

The script is idempotent: parks already present by name are skipped.

API documentation: https://www.nps.gov/subjects/developer/api-documentation.htm
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
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
from app.models.database import Base, Location  # noqa: E402

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("load_nps")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
NPS_API_BASE = "https://developer.nps.gov/api/v1/parks"

# Designations to fetch and their LocationType mapping
DESIGNATION_MAP: Dict[str, str] = {
    "National Battlefield": "battle",
    "National Battlefield Park": "battle",
    "National Battlefield Site": "battle",
    "National Military Park": "battle",
    "National Historic Site": "structure",
    "National Historical Park": "structure",
    "National Monument": "structure",
}

NPS_CONFIDENCE = 0.95  # Highest authority data source
PAGE_SIZE = 50


# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------

async def _fetch_parks_page(
    client: httpx.AsyncClient,
    designation: str,
    api_key: str,
    start: int = 0,
) -> Tuple[List[Dict[str, Any]], int]:
    """
    Fetch one page of parks filtered by designation from the NPS API.

    Returns:
        Tuple of (list of park dicts, total count).
    """
    params = {
        "designation": designation,
        "limit": PAGE_SIZE,
        "start": start,
        "api_key": api_key,
        "fields": "fullName,description,latitude,longitude,designation",
    }
    try:
        response = await client.get(NPS_API_BASE, params=params)
        response.raise_for_status()
        data = response.json()
        return data.get("data", []), int(data.get("total", 0))
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        logger.error("NPS API error for designation %r: %s", designation, exc)
        return [], 0


async def _fetch_all_parks(
    api_key: str,
    timeout: float = 30.0,
) -> List[Dict[str, Any]]:
    """Fetch all parks across all target designations."""
    all_parks: List[Dict[str, Any]] = []

    async with httpx.AsyncClient(timeout=timeout) as client:
        for designation in DESIGNATION_MAP:
            logger.info("Fetching NPS parks with designation: %s", designation)
            start = 0
            designation_count = 0
            while True:
                parks, total = await _fetch_parks_page(
                    client, designation, api_key, start
                )
                if not parks:
                    break
                for park in parks:
                    # Attach the canonical designation so we can map it later
                    park["_designation"] = designation
                all_parks.extend(parks)
                designation_count += len(parks)
                start += len(parks)
                if start >= total:
                    break
            logger.info(
                "  → %d parks fetched for %r", designation_count, designation
            )

    return all_parks


# ---------------------------------------------------------------------------
# Record normalisation
# ---------------------------------------------------------------------------

def _normalise_park(park: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Convert a raw NPS API park dict into a Location insert dict.

    Returns ``None`` if the record is missing required fields.
    """
    name = (park.get("fullName") or "").strip()
    if not name:
        return None

    try:
        lat = float(park["latitude"])
        lon = float(park["longitude"])
    except (ValueError, TypeError, KeyError):
        logger.debug("Skipping %r — no valid coordinates.", name)
        return None

    if lat == 0.0 and lon == 0.0:
        return None

    designation = park.get("_designation", park.get("designation", ""))
    loc_type = DESIGNATION_MAP.get(designation, "structure")
    description = (park.get("description") or "")[:1000]

    return {
        "id": uuid.uuid4(),
        "name": name,
        "type": loc_type,
        "latitude": lat,
        "longitude": lon,
        "description": description,
        "source": "nps",
        "confidence": NPS_CONFIDENCE,
        "geom": f"SRID=4326;POINT({lon} {lat})",
    }


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

async def _load_existing_names(session: AsyncSession) -> Set[str]:
    """Return a set of location names already in the database."""
    result = await session.execute(select(Location.name))
    return {row[0] for row in result}


async def _insert_records(
    session: AsyncSession,
    records: List[Dict[str, Any]],
) -> int:
    """Insert location records, skipping duplicates by name."""
    if not records:
        return 0
    stmt = pg_insert(Location).values(records).on_conflict_do_nothing()
    result = await session.execute(stmt)
    await session.commit()
    return result.rowcount or len(records)


# ---------------------------------------------------------------------------
# Main async entry point
# ---------------------------------------------------------------------------

async def _run(dry_run: bool) -> None:
    api_key = settings.NPS_API_KEY
    if not api_key:
        logger.error(
            "NPS_API_KEY is not set. "
            "Add it to backend/.env or export it as an environment variable."
        )
        sys.exit(1)

    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=False,
        pool_pre_ping=True,
    )
    session_factory = async_sessionmaker(
        bind=engine, class_=AsyncSession, expire_on_commit=False
    )

    # Ensure tables exist
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
        await conn.run_sync(Base.metadata.create_all)

    # Fetch from NPS
    parks = await _fetch_all_parks(api_key)
    logger.info("Total parks fetched from NPS API: %d", len(parks))

    # Normalise
    records = [r for park in parks if (r := _normalise_park(park)) is not None]
    logger.info("Records with valid coordinates: %d", len(records))

    if dry_run:
        for rec in records[:10]:
            logger.info("  [DRY-RUN] %s (type=%s)", rec["name"], rec["type"])
        logger.info("Dry-run complete — no records inserted.")
        await engine.dispose()
        return

    # De-duplicate against existing data
    async with session_factory() as session:
        existing = await _load_existing_names(session)

    unique_records = [r for r in records if r["name"] not in existing]
    logger.info(
        "%d new records to insert (%d already exist).",
        len(unique_records),
        len(records) - len(unique_records),
    )

    if unique_records:
        async with session_factory() as session:
            inserted = await _insert_records(session, unique_records)
        logger.info("Inserted %d NPS records.", inserted)
    else:
        logger.info("No new records to insert.")

    await engine.dispose()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import NPS historic site records into Prescia Maps."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch and parse records but do not write to the database.",
    )
    args = parser.parse_args()

    asyncio.run(_run(dry_run=args.dry_run))


if __name__ == "__main__":
    main()
