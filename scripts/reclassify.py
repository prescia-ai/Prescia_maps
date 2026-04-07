"""
One-shot script to reclassify all Location records in the database
using source-label-first logic.

Run from project root:
    python scripts/reclassify.py [--dry-run] [--source-filter PREFIX]

Classification priority (highest → lowest):
1. Source label  — parse the ``source`` column and map substrings to a type.
2. Name/description classifier — ``classify_event_type(name, description)``.
3. Existing type — kept when both #1 and #2 return a generic type
   (``"event"`` or ``"structure"``).

The script is idempotent: running it twice produces the same result.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from collections import Counter
from typing import Optional

# ---------------------------------------------------------------------------
# Path setup — allow running from the project root without installing the
# backend package.
# ---------------------------------------------------------------------------

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR = os.path.join(os.path.dirname(_SCRIPT_DIR), "backend")
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from sqlalchemy import select

from app.models.database import AsyncSessionLocal, Location, LocationType
from app.scrapers.normalizer import classify_event_type

# ---------------------------------------------------------------------------
# Valid types (derived from the LocationType enum — do NOT modify the enum)
# ---------------------------------------------------------------------------

_VALID_TYPES: frozenset[str] = frozenset(t.value for t in LocationType)

# Generic types that may be overridden by a more specific existing type
_GENERIC_TYPES: frozenset[str] = frozenset({"event", "structure"})

# ---------------------------------------------------------------------------
# Source-label mapping (ordered: more specific patterns first)
# ---------------------------------------------------------------------------

# Each entry is (substring_to_check, type_to_assign).
# The source string is lower-cased before matching.
_SOURCE_RULES: list[tuple[str, str]] = [
    ("ghost_town",             "town"),
    ("mission",                "mission"),
    ("ferry",                  "ferry"),
    ("shipwreck",              "shipwreck"),
    ("trading_post",           "trading_post"),
    ("stagecoach",             "stagecoach_stop"),
    ("pony_express",           "pony_express"),
    # War / battle sources
    ("civil_war",              "battle"),
    ("revolutionary_war",      "battle"),
    ("indian_wars",            "battle"),
    ("war_of_1812",            "battle"),
    ("mexican_american_war",   "battle"),
    ("spanish_american_war",   "battle"),
    # Fort → structure (checked after war patterns to avoid false-positive
    # overlap with "fortification" in battle descriptions)
    ("fort",                   "structure"),
    # Trails
    ("oregon_trail",           "trail"),
    ("california_trail",       "trail"),
    ("mormon_trail",           "trail"),
    ("santa_fe_trail",         "trail"),
    ("el_camino_real",         "trail"),
    ("lewis_clark",            "trail"),
    ("natchez_trace",          "trail"),
    ("old_spanish_trail",      "trail"),
    ("trail",                  "trail"),
    # Generic mine (checked last among mine-related patterns)
    ("mining",                 "mine"),
    ("mine",                   "mine"),
]


def _classify_from_source(source: Optional[str]) -> Optional[str]:
    """
    Return a type string derived from the source label, or None.

    The source column typically looks like ``"wikipedia:ghost_towns_nevada"``
    or ``"wikipedia:missions_texas"``.  We lower-case it and check for
    known substrings in priority order.
    """
    if not source:
        return None
    source_lower = source.lower()
    for substring, type_value in _SOURCE_RULES:
        if substring in source_lower:
            return type_value
    return None


def _best_type(
    source: Optional[str],
    name: str,
    description: Optional[str],
    existing_type: str,
) -> str:
    """
    Determine the best type for a location using three-tier priority.

    1. Source label (most authoritative for scraped Wikipedia data).
    2. Name / description classifier.
    3. Existing type (fallback when #1 and #2 return a generic value).

    Returns a valid ``LocationType`` string.
    """
    # 1. Source-label classification
    source_type = _classify_from_source(source)
    if source_type and source_type not in _GENERIC_TYPES:
        return source_type

    # 2. Name / description classifier
    desc = description or ""
    classifier_type = classify_event_type(name, desc)

    # If the classifier returns a specific (non-generic) type, use it
    if classifier_type not in _GENERIC_TYPES:
        return classifier_type

    # 3. Keep the existing type — it may already be correctly specific
    return existing_type


# ---------------------------------------------------------------------------
# Main async routine
# ---------------------------------------------------------------------------

async def reclassify(dry_run: bool = False, source_filter: Optional[str] = None) -> None:
    """
    Iterate over all Location records and update their ``type`` column.

    Args:
        dry_run:       When True, print changes without committing.
        source_filter: If set, only process records whose source starts with
                       this prefix (e.g. ``"wikipedia:"``).
    """
    # Soft-import tqdm; fall back to a simple identity wrapper if not installed.
    try:
        from tqdm import tqdm as _tqdm_cls  # type: ignore[import]
        _have_tqdm = True
    except ImportError:
        _have_tqdm = False

    def _progress(iterable, total):  # type: ignore[misc]
        if _have_tqdm:
            return _tqdm_cls(iterable, total=total, unit="loc", desc="Reclassifying")
        return iterable

    async with AsyncSessionLocal() as session:
        stmt = select(Location)
        if source_filter:
            stmt = stmt.where(Location.source.like(f"{source_filter}%"))

        result = await session.execute(stmt)
        locations = result.scalars().all()

        total = len(locations)
        updated = 0
        unchanged = 0
        skipped = 0
        type_counter: Counter = Counter()

        for loc in _progress(locations, total):
            existing_str = loc.type.value if hasattr(loc.type, "value") else str(loc.type)
            new_type = _best_type(loc.source, loc.name, loc.description, existing_str)

            # Validate the computed type is in the enum
            if new_type not in _VALID_TYPES:
                skipped += 1
                continue

            if new_type != existing_str:
                if dry_run:
                    print(f"  [DRY-RUN] {loc.name!r}: {existing_str!r} → {new_type!r}  (source={loc.source!r})")
                else:
                    loc.type = new_type
                updated += 1
                type_counter[new_type] += 1
            else:
                unchanged += 1
                type_counter[existing_str] += 1

        if not dry_run:
            await session.commit()

    # --- Summary -----------------------------------------------------------
    label = "[DRY-RUN] " if dry_run else ""
    print(f"\n{label}Reclassification complete")
    print(f"  {label}Updated  : {updated}")
    print(f"  {label}Unchanged: {unchanged}")
    if skipped:
        print(f"  {label}Skipped  : {skipped} (invalid type)")
    print(f"\n{label}Type distribution after {'(simulated) ' if dry_run else ''}commit:")
    for type_name, count in sorted(type_counter.items(), key=lambda x: -x[1]):
        print(f"  {type_name}: {count}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Reclassify Location records using source-label-first logic."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would change without committing to the database.",
    )
    parser.add_argument(
        "--source-filter",
        metavar="PREFIX",
        default=None,
        help="Only reclassify records whose source starts with PREFIX "
             "(e.g. --source-filter wikipedia:).",
    )
    args = parser.parse_args()

    asyncio.run(reclassify(dry_run=args.dry_run, source_filter=args.source_filter))


if __name__ == "__main__":
    main()
