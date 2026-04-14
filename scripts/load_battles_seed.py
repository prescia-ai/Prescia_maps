#!/usr/bin/env python3
"""
Battle seed loader — imports pre-verified US battle locations from
``data/battles_seed.json`` into the Aurik ``locations`` table.

Usage::

    # Full import
    python scripts/load_battles_seed.py

    # Dry-run (parse + count without DB writes)
    python scripts/load_battles_seed.py --dry-run

    # Clear checkpoint and start fresh
    python scripts/load_battles_seed.py --fresh
"""

from __future__ import annotations

import io
import sys

# Force UTF-8 output on Windows to prevent emoji/unicode crashes
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
if sys.stderr.encoding != 'utf-8':
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any, Dict, List

# ---------------------------------------------------------------------------
# Bootstrap: add backend/ to sys.path so we can import app modules
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
    load_existing_names,
    setup_logging,
)

logger = setup_logging("load_battles_seed")

_DATA_FILE = _SCRIPT_DIR.parent / "data" / "battles_seed.json"
BATCH_SIZE = 200


async def run(dry_run: bool = False, fresh: bool = False) -> None:
    """Load battle seed data into the locations table."""

    if not _DATA_FILE.exists():
        logger.error("Seed file not found: %s", _DATA_FILE)
        sys.exit(1)

    logger.info("Loading seed data from %s …", _DATA_FILE)
    with open(_DATA_FILE, encoding="utf-8") as fh:
        records: List[Dict[str, Any]] = json.load(fh)
    logger.info("Loaded %d records from seed file.", len(records))

    engine, session_factory = create_engine_and_session()
    await ensure_tables(engine)

    # ------------------------------------------------------------------
    # Load existing names for deduplication
    # ------------------------------------------------------------------
    logger.info("Loading existing location names for deduplication …")
    async with session_factory() as session:
        existing_names = await load_existing_names(session)
    logger.info("Found %d existing locations in DB.", len(existing_names))

    dedup = DedupIndex(radius_m=500.0)
    for name in existing_names:
        dedup._names.add(dedup._normalise(name))

    # ------------------------------------------------------------------
    # Build insert batch
    # ------------------------------------------------------------------
    batch: List[Dict[str, Any]] = []
    skipped_dup = 0
    skipped_invalid = 0

    for entry in records:
        name = (entry.get("name") or "").strip()
        if not name:
            skipped_invalid += 1
            continue

        try:
            lat = float(entry["latitude"])
            lon = float(entry["longitude"])
        except (KeyError, ValueError, TypeError):
            logger.warning("Skipping %r — missing or invalid coordinates.", name)
            skipped_invalid += 1
            continue

        if dedup.is_duplicate(name, lat, lon):
            skipped_dup += 1
            continue

        dedup.add(name, lat, lon)

        record = build_location_record(
            name=name,
            lat=lat,
            lon=lon,
            source=entry.get("source", "seed:battles"),
            loc_type=entry.get("type", "battle"),
            year=entry.get("year"),
            description=entry.get("description", ""),
            confidence=entry.get("confidence", 0.95),
        )
        batch.append(record)

    logger.info(
        "Prepared %d records (skipped %d duplicates, %d invalid).",
        len(batch), skipped_dup, skipped_invalid,
    )

    # ------------------------------------------------------------------
    # Insert in batches
    # ------------------------------------------------------------------
    total_inserted = 0
    if not dry_run:
        async with session_factory() as session:
            for start in range(0, len(batch), BATCH_SIZE):
                chunk = batch[start:start + BATCH_SIZE]
                total_inserted += await insert_location_batch(session, chunk)
        logger.info("Inserted %d battle records into locations table.", total_inserted)
    else:
        total_inserted = len(batch)
        logger.info("[DRY-RUN] Would insert %d battle records.", total_inserted)

    await engine.dispose()

    label = "[DRY-RUN] " if dry_run else ""
    logger.info(
        "%sDone. Inserted: %d | Duplicates skipped: %d | Invalid skipped: %d",
        label, total_inserted, skipped_dup, skipped_invalid,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import pre-verified US battle locations from battles_seed.json."
    )
    parser.add_argument(
        "--dry-run", action="store_true", default=False,
        help="Parse and count records without writing to the database.",
    )
    parser.add_argument(
        "--fresh", action="store_true", default=False,
        help="(Reserved for future checkpoint use; currently a no-op.)",
    )
    args = parser.parse_args()

    asyncio.run(run(dry_run=args.dry_run, fresh=args.fresh))


if __name__ == "__main__":
    main()
