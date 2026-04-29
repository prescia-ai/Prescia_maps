#!/usr/bin/env python3
"""
Load state-specific seed data into the database.

Usage:
    python scripts/load_seed_state.py OK
    python scripts/load_seed_state.py --state OK
    python scripts/load_seed_state.py --all  # Load all completed states
    python scripts/load_seed_state.py --dry-run OK  # Preview without inserting
    python scripts/load_seed_state.py --mines western  # Load mine seed data
    python scripts/load_seed_state.py --mines western --dry-run  # Preview mines
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
    """Load seed data for a state or region, handling multiple JSON formats.

    ``state_code`` may be a two-letter state code (e.g. ``"OK"``), a region
    name (e.g. ``"western"``), or any other identifier used to locate a seed
    file.

    Supported formats:
      1. Flat array:              [{...}, {...}]
      2. Nested with "locations": {"state": "X", "locations": [{...}]}
      3. Nested with "mines":     {"region": "X", "mines": [{...}]}

    File name patterns tried in order:
      - seed_{code}.json           (e.g. seed_ok.json)
      - seed_{full_state_name}.json (e.g. seed_oklahoma.json)
      - {code}_seed.json           (e.g. battles_seed.json)
      - seed_mines_{code}.json     (e.g. seed_mines_western.json)
    """
    code_lower = state_code.lower()
    code_upper = state_code.upper()

    # Build candidate file paths in priority order
    candidate_files: List[Path] = [
        _DATA_DIR / f"seed_{code_lower}.json",
    ]
    if code_upper in STATE_CODES:
        full_name = STATE_CODES[code_upper].lower().replace(" ", "_")
        candidate_files.append(_DATA_DIR / f"seed_{full_name}.json")
    candidate_files.append(_DATA_DIR / f"{code_lower}_seed.json")
    candidate_files.append(_DATA_DIR / f"seed_mines_{code_lower}.json")

    seed_file = next((f for f in candidate_files if f.exists()), None)
    if seed_file is None:
        tried = ", ".join(f.name for f in candidate_files)
        raise FileNotFoundError(
            f"Seed file not found for {state_code!r}. Tried: {tried}"
        )

    logger.info("Loading seed data for %s from %s", code_upper, seed_file.name)

    with open(seed_file, encoding="utf-8") as fh:
        data: Any = json.load(fh)

    # Auto-detect format and extract the list of location records
    if isinstance(data, list):
        # Format 1: Flat array [{...}, {...}]
        raw_locations: List[Dict[str, Any]] = data
        logger.info("Detected flat array format.")
    elif isinstance(data, dict):
        if "locations" in data:
            # Format 2: Nested with "locations" key
            raw_locations = data["locations"]
            label = data.get("state", code_upper)
            logger.info("Detected nested format with 'locations' array for %s.", label)
        elif "mines" in data:
            # Format 3: Nested with "mines" key
            raw_locations = data["mines"]
            label = data.get("region", code_upper)
            logger.info("Detected nested format with 'mines' array for %s.", label)
        else:
            raise ValueError(
                f"Invalid JSON format in {seed_file.name}: expected array or "
                "object with 'locations' or 'mines' key"
            )
    else:
        raise ValueError(
            f"Invalid JSON format in {seed_file.name}: expected array or object, "
            f"got {type(data).__name__}"
        )

    logger.info("Found %d locations in seed file.", len(raw_locations))

    if dry_run:
        logger.info("[DRY-RUN] Preview for %s:", code_upper)
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

    logger.info("Inserted %d records for %s.", total_inserted, code_upper)
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


async def load_mines_seed(region: str, dry_run: bool = False) -> Dict[str, int]:
    """Load mine seed data for a region."""
    seed_file = _DATA_DIR / f"seed_mines_{region.lower()}.json"

    if not seed_file.exists():
        raise FileNotFoundError(f"Mine seed file not found: {seed_file}")

    logger.info("Loading mine seed data for %r from %s", region, seed_file.name)

    with open(seed_file, encoding="utf-8") as fh:
        data: Dict[str, Any] = json.load(fh)

    raw_mines: List[Dict[str, Any]] = data.get("mines", [])
    logger.info("Found %d mines in seed file.", len(raw_mines))

    if dry_run:
        logger.info("[DRY-RUN] Preview for mines:%s:", region)
        for mine in raw_mines[:10]:
            coords = "%.4f, %.4f" % (mine.get("latitude", 0), mine.get("longitude", 0))
            logger.info(
                "  * %s (%s, %s)  %s",
                mine.get("name", "?"),
                mine.get("commodity", "unknown"),
                mine.get("year", "unknown"),
                coords,
            )
        if len(raw_mines) > 10:
            logger.info("  ... and %d more", len(raw_mines) - 10)
        return {"total": len(raw_mines), "inserted": 0, "skipped": 0}

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

    for entry in raw_mines:
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
            source=f"seed_mines:{region.lower()}",
            loc_type="mine",
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

    logger.info("Inserted %d mine records for region %r.", total_inserted, region)
    await engine.dispose()

    return {
        "total": len(raw_mines),
        "inserted": total_inserted,
        "skipped": skipped_dup + skipped_invalid,
    }


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
        "--mines",
        metavar="REGION",
        help="Load mine seed data for a region (e.g., western).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview records without writing to the database.",
    )

    args = parser.parse_args()

    if args.mines:
        result = asyncio.run(load_mines_seed(args.mines, dry_run=args.dry_run))
        logger.info(
            "Done. %d inserted, %d skipped.", result["inserted"], result["skipped"]
        )
    elif args.all:
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
