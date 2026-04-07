"""
National Register of Historic Places (NRHP) bulk import script.

Fetches records from the publicly accessible NRHP ArcGIS REST service and
imports those relevant to metal detecting into the Prescia Maps database.

Usage::

    python scripts/load_nrhp.py
    python scripts/load_nrhp.py --state TX
    python scripts/load_nrhp.py --limit 500
    python scripts/load_nrhp.py --dry-run
    python scripts/load_nrhp.py --keywords "battlefield,fort,ferry"

The script is idempotent: records already present by name are skipped using
``on_conflict_do_nothing``.

Data source: NRHP ArcGIS FeatureServer (publicly accessible, no API key)
https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services/NRHP_Listings/FeatureServer/0/query
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

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
logger = logging.getLogger("load_nrhp")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

NRHP_API_URL = (
    "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services"
    "/NRHP_Listings/FeatureServer/0/query"
)

# Default keywords for filtering NRHP records to metal-detecting relevant sites
DEFAULT_KEYWORDS: List[str] = [
    "battlefield", "fort", "camp", "post", "mill", "mine", "ferry",
    "tavern", "inn", "trading", "stage", "ranch", "homestead", "bridge",
    "crossing", "cemetery", "church", "mission", "depot", "station",
]

# Map keyword → LocationType value
NRHP_TYPE_MAP: Dict[str, str] = {
    "battlefield": "battle",
    "fort": "structure",
    "camp": "camp",
    "mill": "structure",
    "mine": "mine",
    "ferry": "ferry",
    "tavern": "structure",
    "inn": "structure",
    "trading": "structure",
    "stage": "stagecoach_stop",
    "ranch": "structure",
    "homestead": "structure",
    "bridge": "structure",
    "crossing": "ferry",
    "cemetery": "cemetery",
    "church": "structure",
    "mission": "mission",
    "depot": "railroad_stop",
    "station": "railroad_stop",
}

NRHP_CONFIDENCE = 0.90  # NRHP = high authority data source
PAGE_SIZE = 1000

_HEADERS = {
    "User-Agent": (
        "prescia_maps/1.0 (historical research bot; "
        "https://github.com/prescia/maps)"
    )
}


# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------

async def _fetch_page(
    client: httpx.AsyncClient,
    state: Optional[str],
    offset: int,
) -> List[Dict[str, Any]]:
    """
    Fetch one page of NRHP records from the ArcGIS REST service.

    Args:
        client: Shared httpx async client.
        state:  Two-letter state abbreviation to filter by (or None for all).
        offset: Record offset for pagination.

    Returns:
        List of raw feature attribute dicts.
    """
    where = f"STATE_='{state.upper()}'" if state else "1=1"
    params = {
        "where": where,
        "outFields": "RESNAME,CITY,STATE_,LATITUDE,LONGITUDE,NRHP_REFNUM",
        "f": "json",
        "resultRecordCount": PAGE_SIZE,
        "resultOffset": offset,
    }
    try:
        response = await client.get(NRHP_API_URL, params=params, headers=_HEADERS)
        response.raise_for_status()
        data = response.json()
        features = data.get("features", [])
        return [f.get("attributes", {}) for f in features]
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        logger.error("NRHP API error at offset %d: %s", offset, exc)
        return []


async def _fetch_all_records(
    state: Optional[str],
    limit: Optional[int],
    timeout: float = 30.0,
) -> List[Dict[str, Any]]:
    """Paginate through the NRHP API and return all matching records."""
    all_records: List[Dict[str, Any]] = []
    offset = 0

    async with httpx.AsyncClient(timeout=timeout) as client:
        while True:
            page = await _fetch_page(client, state, offset)
            if not page:
                break
            all_records.extend(page)
            logger.info("  Fetched %d records (total so far: %d)", len(page), len(all_records))
            offset += len(page)

            if len(page) < PAGE_SIZE:
                # Last page
                break
            if limit is not None and len(all_records) >= limit:
                all_records = all_records[:limit]
                break

    return all_records


# ---------------------------------------------------------------------------
# Filtering and normalisation
# ---------------------------------------------------------------------------

def _matches_keywords(name: str, keywords: List[str]) -> bool:
    """Return True if the name contains any of the keywords (case-insensitive)."""
    name_lower = name.lower()
    return any(kw in name_lower for kw in keywords)


def _infer_type(name: str) -> str:
    """
    Infer a LocationType value from the record name based on NRHP_TYPE_MAP.

    Returns the first matching type, or ``"structure"`` as default.
    """
    name_lower = name.lower()
    for keyword, loc_type in NRHP_TYPE_MAP.items():
        if keyword in name_lower:
            return loc_type
    return "structure"


def _normalise_record(attrs: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Convert raw NRHP attribute dict into a Location insert dict.

    Returns ``None`` if required fields are missing or invalid.
    """
    name = (attrs.get("RESNAME") or "").strip()
    if not name:
        return None

    try:
        lat = float(attrs["LATITUDE"])
        lon = float(attrs["LONGITUDE"])
    except (ValueError, TypeError, KeyError):
        logger.debug("Skipping %r — no valid coordinates.", name)
        return None

    if lat == 0.0 and lon == 0.0:
        return None

    city = (attrs.get("CITY") or "").strip()
    state = (attrs.get("STATE_") or "").strip()
    ref_num = (attrs.get("NRHP_REFNUM") or "").strip()

    description_parts = []
    if city:
        description_parts.append(city)
    if state:
        description_parts.append(state)
    if ref_num:
        description_parts.append(f"NRHP #{ref_num}")
    description = ", ".join(description_parts)

    loc_type = _infer_type(name)

    return {
        "id": uuid.uuid4(),
        "name": name,
        "type": loc_type,
        "latitude": lat,
        "longitude": lon,
        "description": description or None,
        "source": "nrhp",
        "confidence": NRHP_CONFIDENCE,
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
    """Insert location records, skipping duplicates (on_conflict_do_nothing)."""
    if not records:
        return 0
    stmt = pg_insert(Location).values(records).on_conflict_do_nothing()
    result = await session.execute(stmt)
    await session.commit()
    return result.rowcount or 0


# ---------------------------------------------------------------------------
# Main async entry point
# ---------------------------------------------------------------------------

async def _run(
    state: Optional[str],
    limit: Optional[int],
    dry_run: bool,
    keywords: List[str],
) -> None:
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=False,
        pool_pre_ping=True,
    )
    session_factory = async_sessionmaker(
        bind=engine, class_=AsyncSession, expire_on_commit=False
    )

    # Ensure tables and enum values exist
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
        await conn.run_sync(Base.metadata.create_all)
        # Ensure new enum values are present (idempotent)
        for val in ["mission", "trading_post", "shipwreck", "pony_express"]:
            await conn.execute(
                text(f"ALTER TYPE location_type_enum ADD VALUE IF NOT EXISTS '{val}'")
            )

    # Fetch raw records from NRHP
    state_label = state.upper() if state else "all states"
    logger.info("Fetching NRHP records for %s ...", state_label)
    raw_records = await _fetch_all_records(state, limit)
    logger.info("Fetched %d raw NRHP records.", len(raw_records))

    # Filter by keywords
    filtered = [r for r in raw_records if _matches_keywords(r.get("RESNAME", ""), keywords)]
    logger.info(
        "%d records match keyword filter (%s).",
        len(filtered),
        ", ".join(keywords[:5]) + ("..." if len(keywords) > 5 else ""),
    )

    # Normalise
    records = [r for attrs in filtered if (r := _normalise_record(attrs)) is not None]
    logger.info("Records with valid coordinates: %d", len(records))

    if dry_run:
        for rec in records[:20]:
            logger.info("  [DRY-RUN] %s (type=%s, source=%s)", rec["name"], rec["type"], rec["source"])
        logger.info("Dry-run complete — %d records would be inserted.", len(records))
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
        logger.info("Inserted %d NRHP records.", inserted)
    else:
        logger.info("No new records to insert.")

    await engine.dispose()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import NRHP historic site records into Prescia Maps."
    )
    parser.add_argument(
        "--state",
        metavar="XX",
        help="Filter by two-letter US state abbreviation (e.g. TX).",
        default=None,
    )
    parser.add_argument(
        "--limit",
        type=int,
        metavar="N",
        help="Maximum number of records to import.",
        default=None,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch and parse records but do not write to the database.",
    )
    parser.add_argument(
        "--keywords",
        metavar="KEYWORDS",
        help=(
            "Comma-separated keyword filter "
            f"(default: {','.join(DEFAULT_KEYWORDS[:5])},...)"
        ),
        default=None,
    )
    args = parser.parse_args()

    keywords = (
        [kw.strip() for kw in args.keywords.split(",") if kw.strip()]
        if args.keywords
        else DEFAULT_KEYWORDS
    )

    asyncio.run(
        _run(
            state=args.state,
            limit=args.limit,
            dry_run=args.dry_run,
            keywords=keywords,
        )
    )


if __name__ == "__main__":
    main()
