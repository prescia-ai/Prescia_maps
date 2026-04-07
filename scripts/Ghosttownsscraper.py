#!/usr/bin/env python3
"""
Ghost Towns & Abandoned Places scraper — single source of truth for all
ghost town, church, cemetery, school, spring, and locale data.

Data sources (in priority order):
1. **USGS GNIS** — National File bulk download, filtered for historical
   populated places, churches, cemeteries, schools, springs, camps, etc.
2. **Legends of America** — state-by-state ghost town listings
3. **Ghosttowns.com** — additional ghost town database

Replaces data previously scattered across:
- ``scrape_wikipedia.py`` / ``scrape_wikipedia_2.py`` (ghost town pages)
- ``load_gnis.py`` (non-mine feature classes)
- ``load_datasets.py`` (HISTORIC_TOWNS where type=town)

Usage::

    # Full import
    python scripts/Ghosttownsscraper.py

    # Filter by state
    python scripts/Ghosttownsscraper.py --state CO

    # Limit records
    python scripts/Ghosttownsscraper.py --limit 5000

    # Dry-run
    python scripts/Ghosttownsscraper.py --dry-run

    # Skip web scraping (GNIS only)
    python scripts/Ghosttownsscraper.py --gnis-only
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import io
import re
import sys
import uuid
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import httpx
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------
_SCRIPT_DIR = Path(__file__).resolve().parent
_BACKEND_DIR = _SCRIPT_DIR.parent / "backend"
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from scraper_utils import (  # noqa: E402
    DedupIndex,
    RateLimiter,
    build_location_record,
    create_engine_and_session,
    ensure_tables,
    insert_location_batch,
    load_checkpoint,
    load_existing_names,
    save_checkpoint,
    setup_logging,
)
from app.scrapers.normalizer import clean_name, is_blocked  # noqa: E402
from app.services import geocoding  # noqa: E402

logger = setup_logging("Ghosttownsscraper")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

GNIS_NATIONAL_FILE_URL = "https://geonames.usgs.gov/docs/stategaz/NationalFile.zip"
GNIS_SOURCE = "gnis"
GNIS_CONFIDENCE = 0.85

# GNIS feature classes relevant to ghost towns & abandoned places
FEATURE_CLASS_MAP: Dict[str, str] = {
    "Populated Place": "town",
    "Locale": "locale",
    "Church": "church",
    "School": "school",
    "Cemetery": "cemetery",
    "Camp": "camp",
    "Spring": "spring",
    "Building": "structure",
    "Falls": "locale",
    "Bridge": "structure",
    "Dam": "structure",
    "Crossing": "ferry",
}

# GNIS column names
_COL_NAME = "FEATURE_NAME"
_COL_CLASS = "FEATURE_CLASS"
_COL_STATE = "STATE_ALPHA"
_COL_LAT = "PRIM_LAT_DEC"
_COL_LON = "PRIM_LONG_DEC"
_COL_COUNTY = "COUNTY_NAME"

BATCH_SIZE = 500

# Legends of America state URLs
_LOA_BASE = "https://www.legendsofamerica.com"
_LOA_STATES_PATH = "/ghost-towns/"
_LOA_USER_AGENT = (
    "prescia_maps/1.0 (historical research; "
    "https://github.com/prescia-ai/Prescia_maps)"
)

# Ghosttowns.com base
_GT_BASE = "https://www.ghosttowns.com"


# ---------------------------------------------------------------------------
# GNIS download & parse
# ---------------------------------------------------------------------------

def _download_gnis(timeout: float = 300.0) -> bytes:
    """Download the GNIS National File ZIP."""
    logger.info("Downloading GNIS National File from %s …", GNIS_NATIONAL_FILE_URL)
    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        response = client.get(GNIS_NATIONAL_FILE_URL)
        response.raise_for_status()
    logger.info("Download complete (%.1f MB).", len(response.content) / 1_048_576)
    return response.content


def _extract_pipe_file(zip_bytes: bytes) -> io.TextIOWrapper:
    """Extract the first .txt file from the GNIS ZIP archive."""
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        txt_names = [n for n in zf.namelist() if n.endswith(".txt")]
        if not txt_names:
            raise ValueError("No .txt file found inside the GNIS ZIP archive.")
        data = zf.read(txt_names[0])
    return io.TextIOWrapper(io.BytesIO(data), encoding="utf-8", errors="replace")


def _parse_gnis_records(
    stream: io.TextIOWrapper,
    state_filter: Optional[str] = None,
    limit: Optional[int] = None,
):
    """
    Yield ghost town / abandoned place records from the GNIS pipe file.

    Filters for feature classes defined in ``FEATURE_CLASS_MAP`` and excludes
    mines (handled by USminesscraper).
    """
    reader = csv.DictReader(stream, delimiter="|")
    accepted = 0

    for row in reader:
        feature_class = (row.get(_COL_CLASS) or "").strip()

        # Skip mines — handled by USminesscraper
        if feature_class == "Mine":
            continue

        type_str = FEATURE_CLASS_MAP.get(feature_class)
        if type_str is None:
            continue

        if state_filter:
            state = (row.get(_COL_STATE) or "").strip().upper()
            if state != state_filter.upper():
                continue

        try:
            lat = float(row[_COL_LAT])
            lon = float(row[_COL_LON])
        except (ValueError, KeyError):
            continue

        if lat == 0.0 and lon == 0.0:
            continue

        name = (row.get(_COL_NAME) or "").strip()
        if not name:
            continue

        state = (row.get(_COL_STATE) or "").strip()
        county = (row.get(_COL_COUNTY) or "").strip()

        yield name, type_str, lat, lon, state, county
        accepted += 1
        if limit is not None and accepted >= limit:
            return


# ---------------------------------------------------------------------------
# Legends of America scraper
# ---------------------------------------------------------------------------

async def _scrape_legends_of_america(
    client: httpx.AsyncClient,
    rate_limiter: RateLimiter,
    limit: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Scrape Legends of America ghost town listings.

    Returns a list of dicts with keys: name, state, description.
    Coordinates are not available from this source (require geocoding).
    """
    records: List[Dict[str, Any]] = []
    headers = {"User-Agent": _LOA_USER_AGENT}

    try:
        rate_limiter.wait()
        response = await client.get(
            f"{_LOA_BASE}{_LOA_STATES_PATH}", headers=headers
        )
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "lxml")

        # Find state links
        state_links = []
        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]
            if "/ghost-towns/" in href and href != _LOA_STATES_PATH:
                if href.startswith("/"):
                    href = f"{_LOA_BASE}{href}"
                state_links.append(href)

        logger.info("Found %d state pages on Legends of America.", len(state_links))

        for state_url in state_links:
            if limit is not None and len(records) >= limit:
                break

            try:
                rate_limiter.wait()
                resp = await client.get(state_url, headers=headers)
                resp.raise_for_status()
                state_soup = BeautifulSoup(resp.text, "lxml")

                # Extract ghost town names from list items and paragraphs
                for li in state_soup.find_all(["li", "p"]):
                    text = li.get_text(strip=True)
                    if len(text) > 10 and len(text) < 500:
                        # Try to extract a town name (first bold text or first link)
                        name_tag = li.find(["b", "strong", "a"])
                        if name_tag:
                            town_name = name_tag.get_text(strip=True)
                            if len(town_name) > 2 and len(town_name) < 100:
                                records.append({
                                    "name": town_name,
                                    "description": text[:500],
                                    "source": "legends_of_america",
                                })
            except (httpx.HTTPError, Exception) as exc:
                logger.debug("Failed to scrape %s: %s", state_url, exc)
                continue

    except (httpx.HTTPError, Exception) as exc:
        logger.warning("Failed to access Legends of America: %s", exc)

    logger.info("Scraped %d ghost town records from Legends of America.", len(records))
    return records


# ---------------------------------------------------------------------------
# Ghosttowns.com scraper
# ---------------------------------------------------------------------------

async def _scrape_ghosttowns_com(
    client: httpx.AsyncClient,
    rate_limiter: RateLimiter,
    limit: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Scrape ghosttowns.com for ghost town data.

    Returns a list of dicts with keys: name, state, description, lat, lon.
    """
    records: List[Dict[str, Any]] = []
    headers = {"User-Agent": _LOA_USER_AGENT}

    # US states for ghosttowns.com URL patterns
    states = [
        "alabama", "alaska", "arizona", "arkansas", "california", "colorado",
        "connecticut", "delaware", "florida", "georgia", "idaho", "illinois",
        "indiana", "iowa", "kansas", "kentucky", "louisiana", "maine",
        "maryland", "massachusetts", "michigan", "minnesota", "mississippi",
        "missouri", "montana", "nebraska", "nevada", "new-hampshire",
        "new-jersey", "new-mexico", "new-york", "north-carolina",
        "north-dakota", "ohio", "oklahoma", "oregon", "pennsylvania",
        "rhode-island", "south-carolina", "south-dakota", "tennessee",
        "texas", "utah", "vermont", "virginia", "washington",
        "west-virginia", "wisconsin", "wyoming",
    ]

    for state_slug in states:
        if limit is not None and len(records) >= limit:
            break

        url = f"{_GT_BASE}/{state_slug}/"
        try:
            rate_limiter.wait()
            resp = await client.get(url, headers=headers)
            if resp.status_code != 200:
                continue

            soup = BeautifulSoup(resp.text, "lxml")
            for a_tag in soup.find_all("a", href=True):
                text = a_tag.get_text(strip=True)
                if len(text) > 2 and len(text) < 100:
                    # Basic heuristic: links within state pages that look like town names
                    href = a_tag["href"]
                    if state_slug in href and text[0].isupper():
                        records.append({
                            "name": text,
                            "description": f"Ghost town in {state_slug.replace('-', ' ').title()}",
                            "source": "ghosttowns_com",
                        })
        except (httpx.HTTPError, Exception) as exc:
            logger.debug("Failed to scrape %s: %s", url, exc)
            continue

    logger.info("Scraped %d ghost town records from ghosttowns.com.", len(records))
    return records


# ---------------------------------------------------------------------------
# Main async entry point
# ---------------------------------------------------------------------------

async def run(
    state_filter: Optional[str] = None,
    limit: Optional[int] = None,
    dry_run: bool = False,
    gnis_only: bool = False,
    checkpoint_path: Optional[Path] = None,
    fresh: bool = False,
) -> None:
    """Download GNIS data and scrape web sources for ghost towns."""

    engine, session_factory = create_engine_and_session()
    await ensure_tables(engine)

    # -----------------------------------------------------------------------
    # Checkpoint
    # -----------------------------------------------------------------------
    ckpt_path = checkpoint_path or Path("ghosttowns_checkpoint.json")
    if fresh and ckpt_path.exists():
        ckpt_path.unlink()
        logger.info("Deleted existing checkpoint (--fresh).")

    ckpt = load_checkpoint(ckpt_path)
    completed_sources = set(ckpt.get("completed_sources", []))
    stats = ckpt.get("stats", {
        "processed": 0, "inserted": 0, "skipped_dup": 0, "skipped_blocked": 0,
    })

    # -----------------------------------------------------------------------
    # Load existing names for dedup
    # -----------------------------------------------------------------------
    logger.info("Loading existing location names for dedup …")
    async with session_factory() as session:
        existing_names = await load_existing_names(session)
    logger.info("Found %d existing records.", len(existing_names))

    dedup = DedupIndex(radius_m=1000.0)
    for name in existing_names:
        dedup._names.add(dedup._normalise(name))

    total_inserted = stats["inserted"]
    total_processed = stats["processed"]
    skipped_dup = stats["skipped_dup"]
    skipped_blocked = stats["skipped_blocked"]

    # ===================================================================
    # Source 1: USGS GNIS
    # ===================================================================
    if "gnis" not in completed_sources:
        logger.info("=== Source 1: USGS GNIS ===")
        zip_bytes = _download_gnis()
        stream = _extract_pipe_file(zip_bytes)

        batch: List[Dict[str, Any]] = []

        async with session_factory() as session:
            for name, type_str, lat, lon, state, county in _parse_gnis_records(
                stream, state_filter, limit
            ):
                cleaned = clean_name(name)
                if not cleaned:
                    continue

                if is_blocked(cleaned, ""):
                    skipped_blocked += 1
                    continue

                if dedup.is_duplicate(cleaned, lat, lon):
                    skipped_dup += 1
                    continue

                dedup.add(cleaned, lat, lon)

                desc_parts = []
                if county:
                    desc_parts.append(f"{county} County")
                if state:
                    desc_parts.append(state)
                description = ", ".join(desc_parts) if desc_parts else None

                record = build_location_record(
                    name=cleaned,
                    lat=lat,
                    lon=lon,
                    source=GNIS_SOURCE,
                    loc_type=type_str,
                    description=description,
                    confidence=GNIS_CONFIDENCE,
                )
                batch.append(record)
                total_processed += 1

                if len(batch) >= BATCH_SIZE:
                    if not dry_run:
                        total_inserted += await insert_location_batch(session, batch)
                    else:
                        total_inserted += len(batch)
                    batch.clear()

                if total_processed % 5000 == 0:
                    logger.info(
                        "GNIS progress: %d processed, %d inserted.",
                        total_processed, total_inserted,
                    )

            # Final batch
            if batch:
                if not dry_run:
                    total_inserted += await insert_location_batch(session, batch)
                else:
                    total_inserted += len(batch)

        completed_sources.add("gnis")
        save_checkpoint(ckpt_path, {
            "completed_sources": list(completed_sources),
            "stats": {
                "processed": total_processed,
                "inserted": total_inserted,
                "skipped_dup": skipped_dup,
                "skipped_blocked": skipped_blocked,
            },
        })
        logger.info("GNIS import complete: %d inserted.", total_inserted)
    else:
        logger.info("GNIS source already completed (checkpoint). Skipping.")

    # ===================================================================
    # Source 2 & 3: Web scraping (Legends of America, Ghosttowns.com)
    # ===================================================================
    if not gnis_only:
        rate_limiter = RateLimiter(min_interval=1.0)

        async with httpx.AsyncClient(timeout=30.0) as client:
            # --- Legends of America ---
            if "legends_of_america" not in completed_sources:
                logger.info("=== Source 2: Legends of America ===")
                web_records = await _scrape_legends_of_america(
                    client, rate_limiter, limit=limit,
                )

                batch: List[Dict[str, Any]] = []
                skipped_no_coords = 0
                async with session_factory() as session:
                    for rec in web_records:
                        cleaned = clean_name(rec["name"])
                        if not cleaned or is_blocked(cleaned, rec.get("description", "")):
                            skipped_blocked += 1
                            continue
                        if dedup.is_duplicate(cleaned):
                            skipped_dup += 1
                            continue
                        # Geocode inline via Wikipedia + Nominatim
                        coords = await geocoding.geocode(cleaned)
                        if not coords:
                            skipped_no_coords += 1
                            continue
                        lat, lon = coords
                        dedup.add(cleaned, lat, lon)
                        record = build_location_record(
                            name=cleaned,
                            lat=lat,
                            lon=lon,
                            source="legends_of_america",
                            loc_type="town",
                            description=rec.get("description"),
                            confidence=0.60,
                        )
                        batch.append(record)
                        total_processed += 1
                        if len(batch) >= BATCH_SIZE:
                            if not dry_run:
                                total_inserted += await insert_location_batch(session, batch)
                            else:
                                total_inserted += len(batch)
                            batch.clear()
                    if batch:
                        if not dry_run:
                            total_inserted += await insert_location_batch(session, batch)
                        else:
                            total_inserted += len(batch)

                logger.info(
                    "Legends of America: %d inserted, %d no coords.",
                    total_inserted, skipped_no_coords,
                )
                completed_sources.add("legends_of_america")
                save_checkpoint(ckpt_path, {
                    "completed_sources": list(completed_sources),
                    "stats": {
                        "processed": total_processed,
                        "inserted": total_inserted,
                        "skipped_dup": skipped_dup,
                        "skipped_blocked": skipped_blocked,
                    },
                })

            # --- Ghosttowns.com ---
            if "ghosttowns_com" not in completed_sources:
                logger.info("=== Source 3: Ghosttowns.com ===")
                web_records = await _scrape_ghosttowns_com(
                    client, rate_limiter, limit=limit,
                )

                batch = []
                skipped_no_coords = 0
                async with session_factory() as session:
                    for rec in web_records:
                        cleaned = clean_name(rec["name"])
                        if not cleaned or is_blocked(cleaned, rec.get("description", "")):
                            skipped_blocked += 1
                            continue
                        if dedup.is_duplicate(cleaned):
                            skipped_dup += 1
                            continue
                        # Geocode inline via Wikipedia + Nominatim
                        coords = await geocoding.geocode(cleaned)
                        if not coords:
                            skipped_no_coords += 1
                            continue
                        lat, lon = coords
                        dedup.add(cleaned, lat, lon)
                        record = build_location_record(
                            name=cleaned,
                            lat=lat,
                            lon=lon,
                            source="ghosttowns_com",
                            loc_type="town",
                            description=rec.get("description"),
                            confidence=0.55,
                        )
                        batch.append(record)
                        total_processed += 1
                        if len(batch) >= BATCH_SIZE:
                            if not dry_run:
                                total_inserted += await insert_location_batch(session, batch)
                            else:
                                total_inserted += len(batch)
                            batch.clear()
                    if batch:
                        if not dry_run:
                            total_inserted += await insert_location_batch(session, batch)
                        else:
                            total_inserted += len(batch)

                logger.info(
                    "Ghosttowns.com: %d total inserted, %d no coords.",
                    total_inserted, skipped_no_coords,
                )
                completed_sources.add("ghosttowns_com")
                save_checkpoint(ckpt_path, {
                    "completed_sources": list(completed_sources),
                    "stats": {
                        "processed": total_processed,
                        "inserted": total_inserted,
                        "skipped_dup": skipped_dup,
                        "skipped_blocked": skipped_blocked,
                    },
                })

    await engine.dispose()

    # Clean up checkpoint on success
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
        description="Import ghost towns & abandoned places into Prescia Maps."
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
        "--gnis-only", action="store_true", default=False,
        help="Only import GNIS data (skip web scraping).",
    )
    parser.add_argument(
        "--checkpoint", default="ghosttowns_checkpoint.json", metavar="PATH",
        help="Checkpoint file path (default: ghosttowns_checkpoint.json).",
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
            gnis_only=args.gnis_only,
            checkpoint_path=Path(args.checkpoint),
            fresh=args.fresh,
        )
    )


if __name__ == "__main__":
    main()
