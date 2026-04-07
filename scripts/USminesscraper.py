#!/usr/bin/env python3
"""
US Mines scraper — single source of truth for all mine data.

Downloads the USGS Mineral Resources Data System (MRDS) bulk CSV and
imports mine site records into the Prescia Maps database.

Replaces mine data previously scattered across:
- ``load_datasets.py`` (MINING_CAMPS, HISTORIC_TOWNS where type=mine)
- ``scrape_wikipedia.py`` / ``scrape_wikipedia_2.py`` (mine-related pages)
- ``load_gnis.py`` (feature_class = "Mine")
- ``load_nrhp.py`` (mine-keyword records)

Usage::

    # Full import (downloads ~100 MB ZIP, imports all US mine records)
    python scripts/USminesscraper.py

    # Filter by state
    python scripts/USminesscraper.py --state CO

    # Limit records (useful for testing)
    python scripts/USminesscraper.py --limit 1000

    # Dry-run: parse and count without inserting
    python scripts/USminesscraper.py --dry-run

    # Resume from checkpoint
    python scripts/USminesscraper.py --checkpoint mines_checkpoint.json

Data source:
    USGS MRDS — https://mrdata.usgs.gov/mrds/mrds-csv.zip
    Contains 800,000+ mine/mineral sites with lat/lon, commodity, status.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import io
import sys
import uuid
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import httpx

# ---------------------------------------------------------------------------
# Bootstrap imports from the shared utility module
# ---------------------------------------------------------------------------
_SCRIPT_DIR = Path(__file__).resolve().parent
_BACKEND_DIR = _SCRIPT_DIR.parent / "backend"
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from scraper_utils import (  # noqa: E402
    DedupIndex,
    build_location_record,
    create_engine_and_session,
    ensure_tables,
    insert_location_batch,
    load_checkpoint,
    load_existing_names,
    progress_bar,
    save_checkpoint,
    setup_logging,
)
from app.scrapers.normalizer import clean_name, is_blocked  # noqa: E402

logger = setup_logging("USminesscraper")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MRDS_CSV_URL = "https://mrdata.usgs.gov/mrds/mrds-csv.zip"
MRDS_SOURCE = "usgs_mrds"
MRDS_CONFIDENCE = 0.85  # USGS data = high authority

BATCH_SIZE = 500

# MRDS column names
_COL_NAME = "site_name"
_COL_LAT = "latitude"
_COL_LON = "longitude"
_COL_COMMODITY = "commod1"
_COL_STATE = "state"
_COL_STATUS = "dev_stat"
_COL_DEP_TYPE = "dep_type"
_COL_COUNTY = "county"

# Commodity codes of interest for metal detecting relevance
_HIGH_VALUE_COMMODITIES = frozenset([
    "gold", "silver", "copper", "lead", "zinc", "iron",
    "tin", "tungsten", "mercury", "coal", "platinum",
    "molybdenum", "manganese", "chromium", "nickel",
    "cobalt", "antimony", "arsenic", "bismuth",
])


# ---------------------------------------------------------------------------
# Download helpers
# ---------------------------------------------------------------------------

def _download_mrds(timeout: float = 600.0) -> bytes:
    """Download the MRDS CSV ZIP and return its raw bytes."""
    logger.info("Downloading USGS MRDS from %s …", MRDS_CSV_URL)
    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        response = client.get(MRDS_CSV_URL)
        response.raise_for_status()
    logger.info("Download complete (%.1f MB).", len(response.content) / 1_048_576)
    return response.content


def _extract_csv(zip_bytes: bytes) -> io.TextIOWrapper:
    """
    Extract the first CSV file from the MRDS ZIP archive and return it
    as a text stream.
    """
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        csv_names = [n for n in zf.namelist() if n.endswith(".csv") or n.endswith(".txt")]
        if not csv_names:
            raise ValueError("No CSV/TXT file found inside the MRDS ZIP archive.")
        logger.info("Extracting %s from archive.", csv_names[0])
        data = zf.read(csv_names[0])
    return io.TextIOWrapper(io.BytesIO(data), encoding="utf-8", errors="replace")


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def _parse_records(
    stream: io.TextIOWrapper,
    state_filter: Optional[str] = None,
    limit: Optional[int] = None,
):
    """
    Yield cleaned mine records from the MRDS CSV stream.

    Each yielded item is a tuple:
        ``(name, lat, lon, commodity, status, state, county)``
    """
    reader = csv.DictReader(stream)
    accepted = 0

    for row in reader:
        # Extract coordinates
        try:
            lat = float(row.get(_COL_LAT, "").strip())
            lon = float(row.get(_COL_LON, "").strip())
        except (ValueError, AttributeError):
            continue

        if lat == 0.0 and lon == 0.0:
            continue

        # Basic US bounding box filter (continental US + Alaska + Hawaii)
        if not (17.0 <= lat <= 72.0 and -180.0 <= lon <= -65.0):
            continue

        # State filter
        state = (row.get(_COL_STATE) or "").strip()
        if state_filter and state.upper() != state_filter.upper():
            continue

        # Name
        name = (row.get(_COL_NAME) or "").strip()
        if not name or name.lower() in ("unknown", "unnamed", "none", "n/a"):
            continue

        commodity = (row.get(_COL_COMMODITY) or "").strip().lower()
        status = (row.get(_COL_STATUS) or "").strip()
        county = (row.get(_COL_COUNTY) or "").strip()

        yield name, lat, lon, commodity, status, state, county
        accepted += 1
        if limit is not None and accepted >= limit:
            return


def _build_description(
    commodity: str, status: str, state: str, county: str,
) -> str:
    """Build a human-readable description from MRDS fields."""
    parts = []
    if commodity:
        parts.append(f"Commodity: {commodity}")
    if status:
        parts.append(f"Status: {status}")
    if county and state:
        parts.append(f"{county} County, {state}")
    elif state:
        parts.append(state)
    return ". ".join(parts)


# ---------------------------------------------------------------------------
# Main async entry point
# ---------------------------------------------------------------------------

async def run(
    state_filter: Optional[str] = None,
    limit: Optional[int] = None,
    dry_run: bool = False,
    checkpoint_path: Optional[Path] = None,
    fresh: bool = False,
) -> None:
    """Download MRDS data and import mine records into the database."""

    engine, session_factory = create_engine_and_session()
    await ensure_tables(engine)

    # -----------------------------------------------------------------------
    # Checkpoint / resume
    # -----------------------------------------------------------------------
    ckpt_path = checkpoint_path or Path("mines_checkpoint.json")
    if fresh and ckpt_path.exists():
        ckpt_path.unlink()
        logger.info("Deleted existing checkpoint (--fresh).")

    ckpt = load_checkpoint(ckpt_path)
    resume_offset = ckpt.get("offset", 0)
    stats = ckpt.get("stats", {"processed": 0, "inserted": 0, "skipped_dup": 0, "skipped_blocked": 0})

    if resume_offset > 0:
        logger.info("Resuming from offset %d (%d previously inserted).", resume_offset, stats["inserted"])

    # -----------------------------------------------------------------------
    # Load existing names for dedup
    # -----------------------------------------------------------------------
    logger.info("Loading existing location names for dedup …")
    async with session_factory() as session:
        existing_names = await load_existing_names(session)
    logger.info("Found %d existing records.", len(existing_names))

    dedup = DedupIndex(radius_m=500.0)
    for name in existing_names:
        dedup._names.add(dedup._normalise(name))

    # -----------------------------------------------------------------------
    # Download & parse
    # -----------------------------------------------------------------------
    zip_bytes = _download_mrds()
    stream = _extract_csv(zip_bytes)

    batch: List[Dict[str, Any]] = []
    total_processed = stats["processed"]
    total_inserted = stats["inserted"]
    skipped_dup = stats["skipped_dup"]
    skipped_blocked = stats["skipped_blocked"]
    current_offset = 0

    logger.info("Parsing MRDS records …")

    async with session_factory() as session:
        for name, lat, lon, commodity, status, state, county in _parse_records(
            stream, state_filter, limit
        ):
            current_offset += 1

            # Skip already-processed records on resume
            if current_offset <= resume_offset:
                continue

            cleaned = clean_name(name)
            if not cleaned:
                continue

            if is_blocked(cleaned, commodity):
                skipped_blocked += 1
                continue

            if dedup.is_duplicate(cleaned, lat, lon):
                skipped_dup += 1
                continue

            dedup.add(cleaned, lat, lon)

            description = _build_description(commodity, status, state, county)

            record = build_location_record(
                name=cleaned,
                lat=lat,
                lon=lon,
                source=MRDS_SOURCE,
                loc_type="mine",
                description=description,
                confidence=MRDS_CONFIDENCE,
            )
            batch.append(record)
            total_processed += 1

            if len(batch) >= BATCH_SIZE:
                if not dry_run:
                    total_inserted += await insert_location_batch(session, batch)
                else:
                    total_inserted += len(batch)
                batch.clear()

                # Save checkpoint
                save_checkpoint(ckpt_path, {
                    "offset": current_offset,
                    "stats": {
                        "processed": total_processed,
                        "inserted": total_inserted,
                        "skipped_dup": skipped_dup,
                        "skipped_blocked": skipped_blocked,
                    },
                })

            if total_processed % 5000 == 0:
                logger.info(
                    "Progress: %d processed, %d inserted, %d dupes, %d blocked.",
                    total_processed, total_inserted, skipped_dup, skipped_blocked,
                )

        # Final batch
        if batch:
            if not dry_run:
                total_inserted += await insert_location_batch(session, batch)
            else:
                total_inserted += len(batch)

    await engine.dispose()

    # Clean up checkpoint on successful completion
    if ckpt_path.exists() and not dry_run:
        ckpt_path.unlink()

    label = "[DRY-RUN] " if dry_run else ""
    logger.info(
        "%sDone. Processed: %d | Inserted: %d | Duplicates: %d | Blocked: %d",
        label, total_processed, total_inserted, skipped_dup, skipped_blocked,
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import USGS MRDS mine records into Prescia Maps."
    )
    parser.add_argument(
        "--state", metavar="XX", default=None,
        help="Two-letter state abbreviation to filter records (e.g. CO, CA).",
    )
    parser.add_argument(
        "--limit", type=int, default=None, metavar="N",
        help="Stop after N accepted records (useful for testing).",
    )
    parser.add_argument(
        "--dry-run", action="store_true", default=False,
        help="Parse records but do not write to the database.",
    )
    parser.add_argument(
        "--checkpoint", default="mines_checkpoint.json", metavar="PATH",
        help="Checkpoint file path (default: mines_checkpoint.json).",
    )
    parser.add_argument(
        "--fresh", action="store_true", default=False,
        help="Delete existing checkpoint and start fresh.",
    )
    args = parser.parse_args()

    asyncio.run(
        run(
            state_filter=args.state,
            limit=args.limit,
            dry_run=args.dry_run,
            checkpoint_path=Path(args.checkpoint),
            fresh=args.fresh,
        )
    )


if __name__ == "__main__":
    main()
