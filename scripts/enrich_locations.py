#!/usr/bin/env python3
"""
Script to enrich all Location records in the database with detailed
descriptions, corrected types, missing coordinates, and years.

Uses the free Wikipedia MediaWiki API (no API key required) to fetch
article extracts for each location.

Run from project root: python scripts/enrich_locations.py

Optional: pip install tqdm (for progress bar)
"""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

import httpx
from geoalchemy2.shape import from_shape
from shapely.geometry import Point
from sqlalchemy import select

from app.models.database import AsyncSessionLocal, Location, create_tables
from app.scrapers.normalizer import (
    assign_confidence,
    classify_event_type,
    normalize_year,
)
from app.services import geocoding, wiki_geocoding

# tqdm is an optional soft dependency — fall back gracefully if absent
try:
    from tqdm import tqdm as _tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False

_WIKI_API_URL = "https://en.wikipedia.org/w/api.php"
_WIKI_HEADERS = {
    "User-Agent": (
        "prescia_maps/1.0 (historical enrichment; "
        "https://github.com/prescia-ai/Prescia_maps)"
    )
}
# Delay between Wikipedia API calls to be respectful (Wikipedia allows ~200 req/s)
_WIKI_API_DELAY = 0.1
# HTTP client timeout in seconds for Wikipedia API requests
_HTTP_TIMEOUT = 15.0
# Upper bound year: only fill years for pre-modern historical sites
# (metal detecting app targets sites from before the 20th century)
_YEAR_UPPER_BOUND = 1950


# ---------------------------------------------------------------------------
# Wikipedia extract helper
# ---------------------------------------------------------------------------

async def fetch_wikipedia_extract(
    name: str, client: httpx.AsyncClient
) -> Optional[str]:
    """Fetch a plain-text Wikipedia article extract for the given name."""
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
        response = await client.get(
            _WIKI_API_URL, params=params, headers=_WIKI_HEADERS
        )
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

    # Step 2: Try Wikipedia search for the closest match
    search_params = {
        "action": "query",
        "list": "search",
        "srsearch": name,
        "srlimit": "1",
        "format": "json",
    }
    try:
        response = await client.get(
            _WIKI_API_URL, params=search_params, headers=_WIKI_HEADERS
        )
        response.raise_for_status()
        data = response.json()
    except (httpx.HTTPError, ValueError):
        return None

    results = data.get("query", {}).get("search", [])
    if results:
        found_title = results[0]["title"]
        params["titles"] = found_title
        try:
            response = await client.get(
                _WIKI_API_URL, params=params, headers=_WIKI_HEADERS
            )
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
# Per-record enrichment logic
# ---------------------------------------------------------------------------

async def enrich_record(
    record: Location,
    client: httpx.AsyncClient,
    args: argparse.Namespace,
) -> dict:
    """Process a single Location record. Returns dict of changes to apply."""
    changes: dict = {}

    # 1. Enrich description
    current_desc = record.description or ""
    if len(current_desc) < args.min_description_length:
        new_desc = await fetch_wikipedia_extract(record.name, client)
        await asyncio.sleep(_WIKI_API_DELAY)  # Respectful rate-limiting between API calls
        if new_desc and len(new_desc) > len(current_desc):
            changes["description"] = new_desc

    # 2. Reclassify type
    desc_for_classify = changes.get("description", current_desc)
    new_type = classify_event_type(record.name, desc_for_classify)
    current_type = (
        record.type.value if hasattr(record.type, "value") else str(record.type)
    )
    # Only reclassify if new type is specific (not generic "event") and different
    if new_type != "event" and new_type != current_type:
        changes["type"] = new_type

    # 3. Fix missing coordinates
    if not args.skip_geocode:
        needs_coords = (
            record.latitude is None
            or record.longitude is None
            or record.latitude == 0
            or record.longitude == 0
            or record.geom is None
        )
        if needs_coords:
            coords = await wiki_geocoding.get_article_coords(record.name)
            if not coords:
                coords = await geocoding.geocode(record.name)
            if coords:
                changes["latitude"] = coords[0]
                changes["longitude"] = coords[1]

    # 4. Fix missing/wrong year
    if record.year is None or record.year == 0:
        desc_text = changes.get("description", current_desc)
        new_year = normalize_year(desc_text)
        if new_year and new_year > 0 and new_year < _YEAR_UPPER_BOUND:
            changes["year"] = new_year

    # 5. Recalculate confidence
    has_coords = (
        changes.get("latitude", record.latitude) is not None
        and changes.get("longitude", record.longitude) is not None
    )
    has_year = changes.get("year", record.year) is not None
    new_confidence = assign_confidence(
        source=record.source or "",
        has_coords=has_coords,
        has_year=has_year,
    )
    if new_confidence != record.confidence:
        changes["confidence"] = new_confidence

    return changes


def apply_changes(record: Location, changes: dict) -> None:
    """Apply a dict of field changes to a Location ORM record in-place."""
    # Collect lat/lon together so geom can be set once both are known
    new_lat = changes.get("latitude", record.latitude)
    new_lon = changes.get("longitude", record.longitude)

    for field, value in changes.items():
        if field == "latitude":
            record.latitude = value
        elif field == "longitude":
            record.longitude = value
        elif field == "type":
            record.type = value
        elif field == "description":
            record.description = value
        elif field == "year":
            record.year = value
        elif field == "confidence":
            record.confidence = value

    # Update PostGIS geometry whenever coordinates changed
    if ("latitude" in changes or "longitude" in changes) and (
        new_lat is not None and new_lon is not None
    ):
        record.geom = from_shape(Point(float(new_lon), float(new_lat)), srid=4326)


# ---------------------------------------------------------------------------
# Checkpoint helpers
# ---------------------------------------------------------------------------

def _load_checkpoint(path: Path) -> dict:
    try:
        with open(path) as fh:
            return json.load(fh)
    except Exception:
        return {"processed_ids": [], "stats": {}}


def _save_checkpoint(path: Path, processed_ids: list, stats: dict) -> None:
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w") as fh:
        json.dump({"processed_ids": processed_ids, "stats": stats}, fh)
    os.replace(tmp, path)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Enrich all Location records with descriptions, corrected types, "
            "missing coordinates, and years via the free Wikipedia API."
        )
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Preview changes without writing to the database.",
    )
    parser.add_argument(
        "--checkpoint",
        default="enrich_checkpoint.json",
        metavar="PATH",
        help="Checkpoint file path (default: enrich_checkpoint.json).",
    )
    parser.add_argument(
        "--fresh",
        action="store_true",
        default=False,
        help="Delete existing checkpoint and start over.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=50,
        metavar="N",
        help="Number of records to process per DB commit (default: 50).",
    )
    parser.add_argument(
        "--min-description-length",
        type=int,
        default=100,
        metavar="N",
        help=(
            "Only enrich records with descriptions shorter than this "
            "(default: 100)."
        ),
    )
    parser.add_argument(
        "--skip-geocode",
        action="store_true",
        default=False,
        help="Skip the coordinate-fixing step (faster if only descriptions are needed).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        metavar="N",
        help="Only process the first N records (useful for testing).",
    )
    args = parser.parse_args()

    if args.dry_run:
        print("🔍 Dry-run mode — no database writes will occur.")

    # Ensure tables exist (no-op if already present)
    await create_tables()

    # -----------------------------------------------------------------------
    # Checkpoint / resume
    # -----------------------------------------------------------------------
    checkpoint_path = Path(args.checkpoint)

    if args.fresh and checkpoint_path.exists():
        checkpoint_path.unlink()
        print("🗑  Deleted existing checkpoint (--fresh).")

    ckpt = _load_checkpoint(checkpoint_path)
    processed_ids: list = ckpt.get("processed_ids", [])
    saved_stats: dict = ckpt.get("stats", {})
    processed_id_set: set = set(processed_ids)  # IDs are stored as strings in the checkpoint

    if processed_ids:
        print(
            f"▶  Resuming: {len(processed_ids)} records already processed."
        )

    # -----------------------------------------------------------------------
    # Load records
    # -----------------------------------------------------------------------
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Location).order_by(Location.name)
        )
        all_records = result.scalars().all()

    if args.limit:
        all_records = all_records[: args.limit]

    total = len(all_records)
    print(f"\n📋 Total records in database: {total}")

    # -----------------------------------------------------------------------
    # Stats accumulators (resume from checkpoint if present)
    # -----------------------------------------------------------------------
    stats = {
        "processed": saved_stats.get("processed", 0),
        "descriptions_enriched": saved_stats.get("descriptions_enriched", 0),
        "types_reclassified": saved_stats.get("types_reclassified", 0),
        "coordinates_found": saved_stats.get("coordinates_found", 0),
        "years_filled": saved_stats.get("years_filled", 0),
        "confidence_updated": saved_stats.get("confidence_updated", 0),
        "skipped": saved_stats.get("skipped", 0),
    }

    # -----------------------------------------------------------------------
    # Progress bar (optional tqdm)
    # -----------------------------------------------------------------------
    pending = [r for r in all_records if str(r.id) not in processed_id_set]
    print(f"⚙  Records to process: {len(pending)}\n")

    if HAS_TQDM:
        pbar = _tqdm(
            total=len(pending),
            unit="rec",
            ncols=90,
            colour="green",
            bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}] {postfix}",
        )
    else:
        pbar = None

    # -----------------------------------------------------------------------
    # Main processing loop
    # -----------------------------------------------------------------------
    batch_changes: list[tuple] = []  # (record, changes_dict)

    async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
        for idx, record in enumerate(pending, 1):
            record_id = str(record.id)

            if pbar:
                pbar.set_postfix_str(record.name[:45], refresh=True)
            elif idx % 50 == 0 or idx == 1:
                pct = int(idx / len(pending) * 100)
                print(
                    f"  [{pct:3d}%] {idx}/{len(pending)} — {record.name[:50]}"
                )

            changes = await enrich_record(record, client, args)

            if not changes:
                stats["skipped"] += 1
            else:
                # Accumulate per-category stats
                if "description" in changes:
                    stats["descriptions_enriched"] += 1
                if "type" in changes:
                    stats["types_reclassified"] += 1
                if "latitude" in changes or "longitude" in changes:
                    stats["coordinates_found"] += 1
                if "year" in changes:
                    stats["years_filled"] += 1
                if "confidence" in changes:
                    stats["confidence_updated"] += 1

                if args.dry_run:
                    # Print what would change without touching the DB
                    print(f"\n  📝 [{record.name}] would change:")
                    for field, val in changes.items():
                        old = getattr(record, field, None)
                        if hasattr(old, "value"):
                            old = old.value
                        new_val = val.value if hasattr(val, "value") else val
                        if field == "description":
                            print(
                                f"     {field}: "
                                f"{str(old)[:60]!r} → {str(new_val)[:60]!r}…"
                            )
                        else:
                            print(f"     {field}: {old!r} → {new_val!r}")
                else:
                    batch_changes.append((record, changes))

            processed_ids.append(record_id)
            processed_id_set.add(record_id)
            stats["processed"] += 1

            if pbar:
                pbar.update(1)

            # Commit batch and save checkpoint
            if not args.dry_run and len(batch_changes) >= args.batch_size:
                async with AsyncSessionLocal() as session:
                    for rec, chg in batch_changes:
                        merged = await session.merge(rec)
                        apply_changes(merged, chg)
                    await session.commit()
                batch_changes.clear()
                _save_checkpoint(checkpoint_path, processed_ids, stats)

    if pbar:
        pbar.close()

    # Flush remaining records in the last partial batch
    if not args.dry_run and batch_changes:
        async with AsyncSessionLocal() as session:
            for rec, chg in batch_changes:
                merged = await session.merge(rec)
                apply_changes(merged, chg)
            await session.commit()
        batch_changes.clear()
        _save_checkpoint(checkpoint_path, processed_ids, stats)

    # Clean up checkpoint after a complete (non-dry-run) run
    if not args.dry_run and checkpoint_path.exists():
        checkpoint_path.unlink()

    # -----------------------------------------------------------------------
    # Summary
    # -----------------------------------------------------------------------
    print(
        f"\n✅ Enrichment complete!\n"
        f"   Records processed:        {stats['processed']}\n"
        f"   Descriptions enriched:    {stats['descriptions_enriched']}\n"
        f"   Types reclassified:       {stats['types_reclassified']}\n"
        f"   Coordinates found:        {stats['coordinates_found']}\n"
        f"   Years filled:             {stats['years_filled']}\n"
        f"   Confidence updated:       {stats['confidence_updated']}\n"
        f"   Skipped (already good):   {stats['skipped']}"
    )


if __name__ == "__main__":
    asyncio.run(main())
