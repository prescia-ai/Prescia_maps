#!/usr/bin/env python3
"""
Script to scrape Wikipedia for historical events and store in database.
Run from project root: python scripts/scrape_wikipedia.py
"""
import argparse
import asyncio
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

import uuid
from app.models.database import AsyncSessionLocal, create_tables
from app.models.database import Location
from app.scrapers.wikipedia import scrape_all
from app.scrapers.normalizer import classify_event_type, assign_confidence, normalize_year, clean_name, is_blocked
from geoalchemy2.shape import from_shape
from shapely.geometry import Point
from sqlalchemy import select

async def main():
    parser = argparse.ArgumentParser(description="Scrape Wikipedia for historical events and store in database.")
    parser.add_argument(
        "--no-geocode",
        action="store_true",
        default=False,
        help="Skip Nominatim geocoding; only insert records with coordinates already present in Wikipedia HTML.",
    )
    args = parser.parse_args()

    print("Creating database tables...")
    await create_tables()

    if args.no_geocode:
        print("Geocoding disabled — only records with embedded coordinates will be inserted.")

    print("Starting Wikipedia scraper...")
    events = await scrape_all(geocode_missing=not args.no_geocode)

    print(f"Found {len(events)} events. Inserting into database...")

    async with AsyncSessionLocal() as session:
        # Bulk-load existing names once instead of one query per record
        result = await session.execute(select(Location.name))
        existing_names = {row[0] for row in result}

        inserted = 0
        skipped_no_coords = 0
        skipped_duplicate = 0
        skipped_blocked = 0

        for event in events:
            name = clean_name(event.get('name', ''))
            if not name:
                skipped_no_coords += 1
                continue

            if is_blocked(name, event.get('description', '')):
                skipped_blocked += 1
                continue

            if name in existing_names:
                skipped_duplicate += 1
                continue

            lat = event.get('latitude')
            lon = event.get('longitude')
            if not lat or not lon:
                skipped_no_coords += 1
                continue

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

        await session.commit()
        print(f"Done. Inserted: {inserted}, Skipped (no coords): {skipped_no_coords}, Skipped (duplicate): {skipped_duplicate}, Skipped (blocked): {skipped_blocked}")

if __name__ == '__main__':
    asyncio.run(main())
