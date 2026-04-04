"""
GNIS bulk data loader — Geographic Names Information System.

Downloads the USGS National File (pipe-delimited) and imports historical
place names into the Prescia Maps database.

Usage::

    # Load all high-value feature classes (nation-wide)
    python scripts/load_gnis.py

    # Load only Colorado
    python scripts/load_gnis.py --state CO

    # Dry-run / smoke test (first 500 records)
    python scripts/load_gnis.py --limit 500

The script is idempotent: records already present (matched by name + type)
are silently skipped.

Requirements:
    - PostgreSQL + PostGIS reachable via DATABASE_URL
    - Python packages: sqlalchemy, asyncpg, geoalchemy2, httpx
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import io
import logging
import sys
import uuid
import zipfile
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
from app.models.database import Location, LocationType  # noqa: E402

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("load_gnis")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
GNIS_NATIONAL_FILE_URL = (
    "https://geonames.usgs.gov/docs/stategaz/NationalFile.zip"
)

# GNIS feature classes to import and their mapping to LocationType
FEATURE_CLASS_MAP: Dict[str, str] = {
    "Mine": "mine",
    "Church": "church",
    "School": "school",
    "Cemetery": "cemetery",
    "Locale": "locale",
    "Building": "structure",
    "Camp": "camp",
    "Spring": "spring",
    "Falls": "locale",
    "Bridge": "structure",
    "Dam": "structure",
    "Park": "event",
    "Crossing": "ferry",
}

# Required GNIS column names
_COL_NAME = "FEATURE_NAME"
_COL_CLASS = "FEATURE_CLASS"
_COL_STATE = "STATE_ALPHA"
_COL_LAT = "PRIM_LAT_DEC"
_COL_LON = "PRIM_LONG_DEC"
_COL_CREATED = "DATE_CREATED"
_COL_EDITED = "DATE_EDITED"

BATCH_SIZE = 500


# ---------------------------------------------------------------------------
# Download helpers
# ---------------------------------------------------------------------------

def _download_national_file(timeout: float = 300.0) -> bytes:
    """Download the GNIS National File ZIP and return its raw bytes."""
    logger.info("Downloading GNIS National File from %s …", GNIS_NATIONAL_FILE_URL)
    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        response = client.get(GNIS_NATIONAL_FILE_URL)
        response.raise_for_status()
    logger.info(
        "Download complete (%.1f MB).", len(response.content) / 1_048_576
    )
    return response.content


def _extract_pipe_file(zip_bytes: bytes) -> io.TextIOWrapper:
    """
    Extract the first .txt pipe-delimited file from a ZIP archive and
    return it as a text stream.
    """
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        txt_names = [n for n in zf.namelist() if n.endswith(".txt")]
        if not txt_names:
            raise ValueError("No .txt file found inside the ZIP archive.")
        data = zf.read(txt_names[0])
    return io.TextIOWrapper(io.BytesIO(data), encoding="utf-8", errors="replace")


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def _parse_records(
    stream: io.TextIOWrapper,
    state_filter: Optional[str],
    limit: Optional[int],
):
    """
    Yield ``(name, type_str, lat, lon)`` tuples from the GNIS pipe file.

    Args:
        stream:       Opened text stream from the extracted ZIP.
        state_filter: If set (e.g. ``"CO"``), only emit records for that state.
        limit:        If set, stop after this many accepted records.
    """
    reader = csv.DictReader(stream, delimiter="|")
    accepted = 0

    for row in reader:
        feature_class = row.get(_COL_CLASS, "").strip()
        type_str = FEATURE_CLASS_MAP.get(feature_class)
        if type_str is None:
            continue

        if state_filter:
            state = row.get(_COL_STATE, "").strip().upper()
            if state != state_filter.upper():
                continue

        try:
            lat = float(row[_COL_LAT])
            lon = float(row[_COL_LON])
        except (ValueError, KeyError):
            continue

        if lat == 0.0 and lon == 0.0:
            continue

        name = row.get(_COL_NAME, "").strip()
        if not name:
            continue

        yield name, type_str, lat, lon
        accepted += 1
        if limit is not None and accepted >= limit:
            return


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

async def _load_existing_keys(session: AsyncSession) -> Set[Tuple[str, str]]:
    """Return a set of (name, type) pairs already in the locations table."""
    result = await session.execute(
        select(Location.name, Location.type)
    )
    return {(row[0], row[1].value if hasattr(row[1], "value") else str(row[1])) for row in result}


async def _insert_batch(
    session: AsyncSession,
    batch: List[Dict[str, Any]],
) -> int:
    """Insert a batch of location dicts, skipping duplicates by name+type."""
    if not batch:
        return 0

    stmt = pg_insert(Location).values(batch)
    stmt = stmt.on_conflict_do_nothing()
    result = await session.execute(stmt)
    await session.commit()
    return result.rowcount or len(batch)


# ---------------------------------------------------------------------------
# Main async entry point
# ---------------------------------------------------------------------------

async def _run(state_filter: Optional[str], limit: Optional[int]) -> None:
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=False,
        pool_pre_ping=True,
    )
    session_factory = async_sessionmaker(
        bind=engine, class_=AsyncSession, expire_on_commit=False
    )

    # Ensure PostGIS and tables exist
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
        from app.models.database import Base
        await conn.run_sync(Base.metadata.create_all)

    logger.info("Loading existing location keys to detect duplicates …")
    async with session_factory() as session:
        existing = await _load_existing_keys(session)
    logger.info("Found %d existing records.", len(existing))

    # Download & parse
    zip_bytes = _download_national_file()
    stream = _extract_pipe_file(zip_bytes)

    batch: List[Dict[str, Any]] = []
    total_processed = 0
    total_inserted = 0
    skipped = 0

    async with session_factory() as session:
        for name, type_str, lat, lon in _parse_records(stream, state_filter, limit):
            key = (name, type_str)
            if key in existing:
                skipped += 1
                continue

            existing.add(key)
            batch.append(
                {
                    "id": uuid.uuid4(),
                    "name": name,
                    "type": type_str,
                    "latitude": lat,
                    "longitude": lon,
                    "source": "gnis",
                    "confidence": 0.85,
                    "geom": f"SRID=4326;POINT({lon} {lat})",
                }
            )
            total_processed += 1

            if len(batch) >= BATCH_SIZE:
                total_inserted += await _insert_batch(session, batch)
                batch.clear()

            if total_processed % 1000 == 0:
                logger.info(
                    "Progress: %d processed, %d inserted, %d skipped.",
                    total_processed,
                    total_inserted,
                    skipped,
                )

        # Final batch
        if batch:
            total_inserted += await _insert_batch(session, batch)

    await engine.dispose()

    logger.info(
        "Done. Processed: %d | Inserted: %d | Skipped (duplicate): %d",
        total_processed,
        total_inserted,
        skipped,
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Load GNIS place names into the Prescia Maps database."
    )
    parser.add_argument(
        "--state",
        metavar="XX",
        default=None,
        help="Two-letter state abbreviation to filter records (e.g. CO, CA).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        metavar="N",
        help="Stop after N accepted records (useful for testing).",
    )
    args = parser.parse_args()

    asyncio.run(_run(state_filter=args.state, limit=args.limit))


if __name__ == "__main__":
    main()
