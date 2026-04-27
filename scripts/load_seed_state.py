#!/usr/bin/env python3
"""
Load state-specific seed data into the database.

Usage:
    python scripts/load_seed_state.py OK
    python scripts/load_seed_state.py --state OK
    python scripts/load_seed_state.py --all  # Load all completed states
    python scripts/load_seed_state.py --dry-run OK  # Preview without inserting
"""

from __future__ import annotations

import io
import sys

# Force UTF-8 output on Windows to prevent emoji/unicode crashes
if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if sys.stderr.encoding != "utf-8":
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

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

logger = setup_logging("load_seed_state")

STATE_CODES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
    "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
    "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho",
    "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
    "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
    "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
    "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
    "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
    "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
    "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah",
    "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
    "WI": "Wisconsin", "WY": "Wyoming",
}

_DATA_DIR = _SCRIPT_DIR.parent / "data"
BATCH_SIZE = 200


async def load_state_seed(
    state_code: str, dry_run: bool = False
) -> Dict[str, int]:
    """Load seed data for a single state and return insert/skip counts."""
    state_code = state_code.upper()
    if state_code not in STATE_CODES:
        raise ValueError(f"Invalid state code: {state_code}")

    seed_file = _DATA_DIR / f"seed_{state_code.lower()}.json"
    if not seed_file.exists():
        raise FileNotFoundError(f"Seed file not found: {seed_file}")

    state_name = STATE_CODES[state_code]
    logger.info("Loading seed data for %s from %s", state_name, seed_file.name)

    with open(seed_file, encoding="utf-8") as fh:
        data: Dict[str, Any] = json.load(fh)

    raw_locations: List[Dict[str, Any]] = data.get("locations", [])
    logger.info("Found %d locations in seed file.", len(raw_locations))

    if dry_run:
        logger.info("[DRY-RUN] Preview for %s:", state_name)
        for loc in raw_locations:
            coords = "%.4f, %.4f" % (loc.get("latitude", 0), loc.get("longitude", 0))
            logger.info(
                "  * %s (%s, %s)  %s",
                loc.get("name", "?"),
                loc.get("type", "?"),
                loc.get("year", "unknown"),
                coords,
            )
        return {"total": len(raw_locations), "inserted": 0, "skipped": 0}

    engine, session_factory = create_engine_and_session()
    await ensure_tables(engine)

    async with session_factory() as session:
        existing_names = await load_existing_names(session)
    logger.info("Found %d existing locations in DB.", len(existing_names))

    dedup = DedupIndex(radius_m=500.0)
    for name in existing_names:
        dedup._names.add(dedup._normalise(name))

    batch: List[Dict[str, Any]] = []
    skipped_dup = 0
    skipped_invalid = 0

    for entry in raw_locations:
        name = (entry.get("name") or "").strip()
        if not name:
            skipped_invalid += 1
            continue

        try:
            lat = float(entry["latitude"])
            lon = float(entry["longitude"])
        except (KeyError, ValueError, TypeError):
            logger.warning("Skipping %r - missing or invalid coordinates.", name)
            skipped_invalid += 1
            continue

        if dedup.is_duplicate(name, lat, lon):
            logger.info("  Skipping duplicate: %s", name)
            skipped_dup += 1
            continue

        dedup.add(name, lat, lon)

        record = build_location_record(
            name=name,
            lat=lat,
            lon=lon,
            source=f"seed_state:{state_code}",
            loc_type=entry.get("type", "locale"),
            year=entry.get("year"),
            description=entry.get("description", ""),
            confidence=entry.get("confidence", 0.9),
        )
        batch.append(record)

    logger.info(
        "Prepared %d records (skipped %d duplicates, %d invalid).",
        len(batch), skipped_dup, skipped_invalid,
    )

    total_inserted = 0
    async with session_factory() as session:
        for start in range(0, len(batch), BATCH_SIZE):
            chunk = batch[start : start + BATCH_SIZE]
            total_inserted += await insert_location_batch(session, chunk)

    logger.info("Inserted %d records for %s.", total_inserted, state_name)
    await engine.dispose()

    return {
        "total": len(raw_locations),
        "inserted": total_inserted,
        "skipped": skipped_dup + skipped_invalid,
    }


async def load_all_states(dry_run: bool = False) -> None:
    """Load all available state seed files found in the data/ directory."""
    seed_files = sorted(_DATA_DIR.glob("seed_*.json"))

    if not seed_files:
        logger.info("No state seed files found in %s", _DATA_DIR)
        return

    logger.info("Found %d state seed file(s).", len(seed_files))

    total_inserted = 0
    total_skipped = 0

    for seed_file in seed_files:
        state_code = seed_file.stem.replace("seed_", "").upper()
        if state_code not in STATE_CODES:
            logger.warning("Unrecognised state code in filename: %s — skipping.", seed_file.name)
            continue

        try:
            result = await load_state_seed(state_code, dry_run=dry_run)
            total_inserted += result["inserted"]
            total_skipped += result["skipped"]
            logger.info(
                "  %s: %d inserted, %d skipped.",
                state_code, result["inserted"], result["skipped"],
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("  Failed to load %s: %s", state_code, exc)

    logger.info(
        "=== Total: %d inserted, %d skipped ===", total_inserted, total_skipped
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Load state-specific seed data into the locations database."
    )
    parser.add_argument(
        "state",
        nargs="?",
        help="Two-letter state code (e.g., OK, TX).",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Load all available state seed files from data/.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview records without writing to the database.",
    )

    args = parser.parse_args()

    if args.all:
        asyncio.run(load_all_states(dry_run=args.dry_run))
    elif args.state:
        result = asyncio.run(load_state_seed(args.state, dry_run=args.dry_run))
        logger.info(
            "Done. %d inserted, %d skipped.", result["inserted"], result["skipped"]
        )
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
