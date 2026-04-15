#!/usr/bin/env python3
"""
Stagecoach route GeoJSON loader — imports stagecoach route LineString features
from ``data/stagecoach_routes.geojson`` into the Aurik
``linear_features`` table.

Usage::

    # Full import
    python scripts/load_stagecoach_geojson.py

    # Dry-run (parse + count without DB writes)
    python scripts/load_stagecoach_geojson.py --dry-run
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
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Bootstrap: add backend/ to sys.path so we can import app modules
# ---------------------------------------------------------------------------
_SCRIPT_DIR = Path(__file__).resolve().parent
_BACKEND_DIR = _SCRIPT_DIR.parent / "backend"
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from scraper_utils import (  # noqa: E402
    create_engine_and_session,
    ensure_tables,
    insert_linear_feature_batch,
    load_existing_linear_feature_names,
    setup_logging,
)

logger = setup_logging("load_stagecoach_geojson")

_DATA_FILE = _SCRIPT_DIR.parent / "data" / "stagecoach_routes.geojson"


def _geojson_feature_to_linear_feature(
    feature: Dict[str, Any],
    existing_names: set,
) -> Optional[Dict[str, Any]]:
    """Convert a GeoJSON LineString feature to a LinearFeature insert dict."""
    props = feature.get("properties") or {}
    name = (props.get("name") or "").strip()
    if not name:
        logger.warning("Skipping feature with missing name: %s", feature)
        return None

    if name in existing_names:
        logger.info("Skipping %r — already in database.", name)
        return None

    geometry = feature.get("geometry") or {}
    if geometry.get("type") != "LineString":
        logger.warning("Skipping %r — geometry type is not LineString.", name)
        return None

    coordinates = geometry.get("coordinates", [])
    if len(coordinates) < 2:
        logger.warning("Skipping %r — fewer than 2 coordinates.", name)
        return None

    try:
        from geoalchemy2.shape import from_shape
        from shapely.geometry import LineString

        line = LineString(coordinates)
        geom = from_shape(line, srid=4326)
    except Exception as exc:
        logger.error("Failed to create geometry for %r: %s", name, exc)
        return None

    feat_type = props.get("type", "road")
    source = props.get("source", "AURIK")

    return {
        "id": uuid.uuid4(),
        "name": name,
        "type": feat_type,
        "geom": geom,
        "source": source,
    }


async def run(dry_run: bool = False) -> None:
    """Load stagecoach route GeoJSON into the linear_features table."""

    if not _DATA_FILE.exists():
        logger.error("GeoJSON file not found: %s", _DATA_FILE)
        sys.exit(1)

    logger.info("Loading GeoJSON from %s …", _DATA_FILE)
    with open(_DATA_FILE, encoding="utf-8") as fh:
        geojson: Dict[str, Any] = json.load(fh)

    features = geojson.get("features", [])
    logger.info("Found %d features in GeoJSON.", len(features))

    engine, session_factory = create_engine_and_session()
    await ensure_tables(engine)

    # ------------------------------------------------------------------
    # Load existing linear feature names for deduplication
    # ------------------------------------------------------------------
    logger.info("Loading existing linear feature names for deduplication …")
    async with session_factory() as session:
        existing_names = await load_existing_linear_feature_names(session)
    logger.info("Found %d existing linear features in DB.", len(existing_names))

    # ------------------------------------------------------------------
    # Build insert batch
    # ------------------------------------------------------------------
    batch: List[Dict[str, Any]] = []
    skipped = 0

    for feature in features:
        record = _geojson_feature_to_linear_feature(feature, existing_names)
        if record is None:
            skipped += 1
            continue
        batch.append(record)

    logger.info(
        "Prepared %d linear feature records (skipped %d).",
        len(batch), skipped,
    )

    # ------------------------------------------------------------------
    # Insert
    # ------------------------------------------------------------------
    total_inserted = 0
    if not dry_run:
        async with session_factory() as session:
            total_inserted = await insert_linear_feature_batch(session, batch)
        logger.info("Inserted %d stagecoach route records.", total_inserted)
    else:
        total_inserted = len(batch)
        logger.info("[DRY-RUN] Would insert %d stagecoach route records.", total_inserted)

    await engine.dispose()

    label = "[DRY-RUN] " if dry_run else ""
    logger.info("%sDone. Inserted: %d | Skipped: %d", label, total_inserted, skipped)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import stagecoach route GeoJSON LineStrings into linear_features table."
    )
    parser.add_argument(
        "--dry-run", action="store_true", default=False,
        help="Parse and count records without writing to the database.",
    )
    args = parser.parse_args()

    asyncio.run(run(dry_run=args.dry_run))


if __name__ == "__main__":
    main()
