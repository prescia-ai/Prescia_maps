#!/usr/bin/env python3
"""
Script to scrape Wikipedia for historical events and store in database.
Run from project root: python scripts/scrape_wikipedia.py

Optional dependency for Phase-1 progress bar:
    pip install tqdm
If tqdm is not installed the script falls back to plain print() lines.
"""
import argparse
import asyncio
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

import uuid
from app.models.database import AsyncSessionLocal, create_tables
from app.models.database import Location
from app.scrapers.wikipedia import WIKIPEDIA_PAGES, scrape_source
from app.scrapers.normalizer import classify_event_type, assign_confidence, normalize_year, clean_name, is_blocked
from geoalchemy2.shape import from_shape
from shapely.geometry import Point
from sqlalchemy import select

# tqdm is an optional soft dependency — fall back gracefully if absent
try:
    from tqdm import tqdm as _tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False


async def main():
    parser = argparse.ArgumentParser(description="Scrape Wikipedia for historical events and store in database.")
    parser.add_argument(
        "--no-geocode",
        action="store_true",
        default=False,
        help="Skip Nominatim geocoding; only insert records with coordinates already present in Wikipedia HTML.",
    )
    args = parser.parse_args()

    print("⚙  Creating database tables...")
    await create_tables()

    if args.no_geocode:
        print("⚠  Geocoding disabled — only records with embedded coordinates will be inserted.")

    total_sources = len(WIKIPEDIA_PAGES)
    print(f"\n🌐 Scraping {total_sources} Wikipedia sources...\n")

    # -----------------------------------------------------------------------
    # Phase 1 — Scraping (one tick per Wikipedia source)
    # -----------------------------------------------------------------------
    all_events = []

    if HAS_TQDM:
        pbar = _tqdm(
            total=total_sources,
            unit="source",
            ncols=90,
            colour="cyan",
            bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}] {postfix}",
        )
    else:
        pbar = None

    for page_config in WIKIPEDIA_PAGES:
        label = page_config.get("source", page_config["url"].split("/")[-1])

        if pbar:
            pbar.set_postfix_str(label[:50], refresh=True)
        else:
            print(f"  → Fetching: {label}")

        try:
            events = await scrape_source(page_config, geocode_missing=not args.no_geocode)
            all_events.extend(events)
            if pbar:
                pbar.set_postfix_str(f"{label[:40]} (+{len(events)})", refresh=True)
            else:
                print(f"     ✓ {len(events)} records")
        except Exception as exc:
            if pbar:
                pbar.set_postfix_str(f"✗ {label[:35]}: {exc}", refresh=True)
            else:
                print(f"     ✗ Failed: {exc}")

        if pbar:
            pbar.update(1)

    if pbar:
        pbar.close()

    print(f"\n📦 Found {len(all_events)} total records. Inserting into database...\n")

    # -----------------------------------------------------------------------
    # Phase 2 — DB insert with live inline status bar
    # -----------------------------------------------------------------------
    async with AsyncSessionLocal() as session:
        # Bulk-load existing names once instead of one query per record
        result = await session.execute(select(Location.name))
        existing_names = {row[0] for row in result}

        inserted = 0
        skipped_no_coords = 0
        skipped_duplicate = 0
        skipped_blocked = 0
        total = len(all_events)

        for i, event in enumerate(all_events, 1):
            name = clean_name(event.get('name', ''))
            if not name:
                skipped_no_coords += 1
            elif is_blocked(name, event.get('description', '')):
                skipped_blocked += 1
            elif name in existing_names:
                skipped_duplicate += 1
            else:
                lat = event.get('latitude')
                lon = event.get('longitude')
                if not lat or not lon:
                    skipped_no_coords += 1
                else:
                    event_type = classify_event_type(name, event.get('description', ''))
                    year = normalize_year(str(event.get('year', '')))
                    confidence = assign_confidence(
                        source=event.get('source', 'wikipedia'),
                        has_coords=True,
                        has_year=year is not None
                    )
                    location = Location(
                        id=uuid.uuid4(),
                        name=name,
                        type=event_type,
                        latitude=float(lat),
                        longitude=float(lon),
                        year=year,
                        description=event.get('description', ''),
                        source=event.get('source', 'Wikipedia'),
                        confidence=confidence,
                        geom=from_shape(Point(float(lon), float(lat)), srid=4326)
                    )
                    session.add(location)
                    existing_names.add(name)  # prevent duplicate inserts within this batch
                    inserted += 1

            # Live status line — updates in-place via carriage return
            if total > 0:
                pct = int(i / total * 100)
                filled = pct // 5
                bar = "█" * filled + "░" * (20 - filled)
                sys.stdout.write(
                    f"\r  [{bar}] {pct:3d}%  "
                    f"✓ {inserted} inserted  "
                    f"⟳ {skipped_duplicate} dupes  "
                    f"✗ {skipped_no_coords} no-coords  "
                    f"⊘ {skipped_blocked} blocked"
                )
                sys.stdout.flush()

        await session.commit()

    # Final summary
    print(f"\n\n✅ Done!")
    print(f"   Inserted:    {inserted}")
    print(f"   Duplicates:  {skipped_duplicate}")
    print(f"   No coords:   {skipped_no_coords}")
    print(f"   Blocked:     {skipped_blocked}")


if __name__ == '__main__':
    asyncio.run(main())
