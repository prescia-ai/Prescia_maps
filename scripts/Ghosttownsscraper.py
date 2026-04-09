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

import io
import sys

# Force UTF-8 output on Windows to prevent emoji/unicode crashes
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
if sys.stderr.encoding != 'utf-8':
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import argparse
import asyncio
import csv
import re
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

GNIS_NATIONAL_FILE_URL = "https://prd-tnm.s3.amazonaws.com/StagedProducts/GeographicNames/DomesticNames/DomesticNames_National_Text.zip"
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

# GNIS column name candidates (new AllNames file may differ from old NationalFile)
_GNIS_NAME_CANDIDATES = ["FEATURE_NAME", "Feature_Name", "feature_name", "NAME", "Name", "GNIS_Name"]
_GNIS_CLASS_CANDIDATES = ["FEATURE_CLASS", "Feature_Class", "feature_class", "CLASS", "Class"]
_GNIS_STATE_CANDIDATES = ["STATE_ALPHA", "State_Alpha", "state_alpha", "STATE", "State"]
_GNIS_LAT_CANDIDATES = ["PRIM_LAT_DEC", "Prim_Lat_Dec", "prim_lat_dec", "LATITUDE", "Latitude", "LAT", "Lat"]
_GNIS_LON_CANDIDATES = ["PRIM_LONG_DEC", "Prim_Long_Dec", "prim_long_dec", "LONGITUDE", "Longitude", "LON", "Lon", "LONG", "Long"]
_GNIS_COUNTY_CANDIDATES = ["COUNTY_NAME", "County_Name", "county_name", "COUNTY", "County"]

BATCH_SIZE = 500

# Legends of America state URLs
_LOA_BASE = "https://www.legendsofamerica.com"
_LOA_STATES_PATH = "/ghost-towns/"
_LOA_USER_AGENT = (
    "prescia_maps/1.0 (historical research; "
    "https://github.com/prescia-ai/Prescia_maps)"
)

# Minimum number of state pages we expect to find via dynamic discovery.
# When fewer are found, the hardcoded slug list is used as a supplement.
_MIN_EXPECTED_STATE_PAGES = 10

# Hardcoded state ghost-town page slugs for Legends of America.
# These follow the pattern /ghost-towns/{slug}/ on legendsofamerica.com.
# Used as a reliable fallback when dynamic link-discovery finds fewer than
# _MIN_EXPECTED_STATE_PAGES state pages.
_LOA_STATE_SLUGS: List[str] = [
    "al-ghosttowns", "ak-ghosttowns", "az-ghosttowns", "ar-ghosttowns",
    "ca-ghosttowns", "co-ghosttowns", "ct-ghosttowns", "de-ghosttowns",
    "fl-ghosttowns", "ga-ghosttowns", "id-ghosttowns", "il-ghosttowns",
    "in-ghosttowns", "ia-ghosttowns", "ks-ghosttowns", "ky-ghosttowns",
    "la-ghosttowns", "me-ghosttowns", "md-ghosttowns", "ma-ghosttowns",
    "mi-ghosttowns", "mn-ghosttowns", "ms-ghosttowns", "mo-ghosttowns",
    "mt-ghosttowns", "ne-ghosttowns", "nv-ghosttowns", "nh-ghosttowns",
    "nj-ghosttowns", "nm-ghosttowns", "ny-ghosttowns", "nc-ghosttowns",
    "nd-ghosttowns", "oh-ghosttowns", "ok-ghosttowns", "or-ghosttowns",
    "pa-ghosttowns", "ri-ghosttowns", "sc-ghosttowns", "sd-ghosttowns",
    "tn-ghosttowns", "tx-ghosttowns", "ut-ghosttowns", "vt-ghosttowns",
    "va-ghosttowns", "wa-ghosttowns", "wv-ghosttowns", "wi-ghosttowns",
    "wy-ghosttowns",
]

# Ghosttowns.com base
_GT_BASE = "https://www.ghosttowns.com"

# Compiled regex for LOA state page links: /ghost-towns/{2-letter-state-code}-...
_LOA_STATE_PAGE_RE = re.compile(r"/ghost-towns/[a-z]{2}-", re.IGNORECASE)

# Compiled regex to reject navigation/category words in extracted town names
_LOA_NAV_WORDS_RE = re.compile(
    r"\b(history|travel|blog|media|resources|contact|about|support|photo|show|more)\b",
    re.IGNORECASE,
)

# Known non-ghost-town strings from Legends of America nav/sidebar
_LOA_JUNK_NAMES: frozenset[str] = frozenset({
    "about us", "about us/more", "social media", "travel blog",
    "resources & credits", "resources", "credits", "contact",
    "home", "privacy policy", "disclaimer", "search",
    "20th century history", "discovery and exploration",
    "exploration of america", "overland trails", "spanish exploration",
    "westward expansion", "early america", "historic people",
    "african americans", "cowboys & trail blazers", "gunfighters",
    "heroes and patriots", "native americans", "presidents of the united states",
    "heroes and leaders", "indian wars", "myths & legends",
    "notable native americans", "old west", "feuds & range wars",
    "american automobile history", "byways & historic trails",
    "the railroad crosses america", "stagecoaches of the american west",
})


def _find_gnis_col(fieldnames, candidates):
    """Find the first matching column name (case-insensitive) from candidates."""
    if not fieldnames:
        return None
    lower_map = {f.lower().strip(): f for f in fieldnames}
    for c in candidates:
        if c.lower() in lower_map:
            return lower_map[c.lower()]
    return None


# ---------------------------------------------------------------------------
# GNIS download & parse
# ---------------------------------------------------------------------------

def _download_gnis(timeout: float = 300.0, max_attempts: int = 3) -> bytes:
    """Download the GNIS National File ZIP with exponential-backoff retry."""
    import time as _time

    last_exc: Exception = RuntimeError("No attempts made")
    for attempt in range(1, max_attempts + 1):
        try:
            logger.info(
                "Downloading GNIS National File from %s (attempt %d/%d) …",
                GNIS_NATIONAL_FILE_URL, attempt, max_attempts,
            )
            with httpx.Client(timeout=timeout, follow_redirects=True) as client:
                response = client.get(GNIS_NATIONAL_FILE_URL)
                response.raise_for_status()
            logger.info("Download complete (%.1f MB).", len(response.content) / 1_048_576)
            return response.content
        except Exception as exc:
            last_exc = exc
            if attempt < max_attempts:
                wait = 2 ** attempt  # 2, 4, 8 seconds
                logger.warning(
                    "GNIS download attempt %d/%d failed: %s — retrying in %ds …",
                    attempt, max_attempts, exc, wait,
                )
                _time.sleep(wait)
            else:
                logger.warning(
                    "GNIS download failed after %d attempts: %s",
                    max_attempts, exc,
                )
    raise last_exc


def _extract_pipe_file(zip_bytes: bytes) -> io.TextIOWrapper:
    """Extract the first .txt file from the GNIS ZIP archive."""
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        txt_names = [n for n in zf.namelist() if n.endswith(".txt")]
        if not txt_names:
            raise ValueError("No .txt file found inside the GNIS ZIP archive.")
        data = zf.read(txt_names[0])
    return io.TextIOWrapper(io.BytesIO(data), encoding="utf-8-sig", errors="replace")


def _detect_gnis_delimiter(stream: io.TextIOWrapper) -> str:
    """Peek at the first line to detect the delimiter (|, tab, or comma)."""
    first_line = stream.readline()
    stream.seek(0)
    if "|" in first_line:
        return "|"
    if "\t" in first_line:
        return "\t"
    return ","


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
    delimiter = _detect_gnis_delimiter(stream)
    reader = csv.DictReader(stream, delimiter=delimiter)
    logger.info("GNIS columns found: %s", reader.fieldnames)

    col_name = _find_gnis_col(reader.fieldnames, _GNIS_NAME_CANDIDATES)
    col_class = _find_gnis_col(reader.fieldnames, _GNIS_CLASS_CANDIDATES)
    col_state = _find_gnis_col(reader.fieldnames, _GNIS_STATE_CANDIDATES)
    col_lat = _find_gnis_col(reader.fieldnames, _GNIS_LAT_CANDIDATES)
    col_lon = _find_gnis_col(reader.fieldnames, _GNIS_LON_CANDIDATES)
    col_county = _find_gnis_col(reader.fieldnames, _GNIS_COUNTY_CANDIDATES)

    if not all([col_name, col_class, col_lat, col_lon]):
        logger.warning(
            "GNIS: could not locate required columns in header — skipping. "
            "Available fields: %s", reader.fieldnames
        )
        return

    accepted = 0

    for row in reader:
        feature_class = (row.get(col_class) or "").strip()

        # Skip mines — handled by USminesscraper
        if feature_class == "Mine":
            continue

        type_str = FEATURE_CLASS_MAP.get(feature_class)
        if type_str is None:
            continue

        if state_filter:
            state = (row.get(col_state) or "").strip().upper() if col_state else ""
            if state != state_filter.upper():
                continue

        try:
            lat = float(row[col_lat])
            lon = float(row[col_lon])
        except (ValueError, KeyError):
            continue

        if lat == 0.0 and lon == 0.0:
            continue

        name = (row.get(col_name) or "").strip()
        if not name:
            continue

        state = (row.get(col_state) or "").strip() if col_state else ""
        county = (row.get(col_county) or "").strip() if col_county else ""

        yield name, type_str, lat, lon, state, county
        accepted += 1
        if limit is not None and accepted >= limit:
            return


def _loa_alternate_url(url: str) -> str:
    """
    Return an alternate form of a Legends of America URL by toggling the
    ``.html`` suffix.  Used to retry 404 responses with the other variant.

    Examples::

        "https://…/al-ghosttowns"      →  "https://…/al-ghosttowns.html"
        "https://…/al-ghosttowns.html" →  "https://…/al-ghosttowns/"
    """
    if url.endswith(".html"):
        return url[: -len(".html")] + "/"
    return url.rstrip("/") + ".html"


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

    # Try to discover state links dynamically from the index page first.
    # Fall back to the hardcoded slug list when fewer than 10 pages are found
    # (the index page structure changes occasionally).
    state_links: List[str] = []
    try:
        rate_limiter.wait()
        response = await client.get(
            f"{_LOA_BASE}{_LOA_STATES_PATH}", headers=headers
        )
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "lxml")

        # Find state-specific ghost town links.
        # LOA state pages follow a consistent pattern like:
        #   /ghost-towns/al-ghosttowns.html  (two-letter state code prefix)
        # Reject generic navigation links that happen to contain /ghost-towns/.
        seen_urls: Set[str] = set()
        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]
            if _LOA_STATE_PAGE_RE.search(href):
                if href.startswith("/"):
                    href = f"{_LOA_BASE}{href}"
                if href not in seen_urls:
                    seen_urls.add(href)
                    state_links.append(href)

        logger.info(
            "Found %d state pages on Legends of America (dynamic).", len(state_links)
        )

        # If dynamic discovery found fewer than the expected number of pages,
        # the index structure has likely changed — supplement with the hardcoded slug list.
        if len(state_links) < _MIN_EXPECTED_STATE_PAGES:
            logger.info(
                "Dynamic discovery found only %d page(s); supplementing with "
                "hardcoded state slug list (%d slugs).",
                len(state_links), len(_LOA_STATE_SLUGS),
            )
            existing = {u.rstrip("/").rstrip(".html") for u in state_links}
            for slug in _LOA_STATE_SLUGS:
                for suffix in ("", ".html"):
                    candidate = f"{_LOA_BASE}/ghost-towns/{slug}{suffix}"
                    candidate_key = candidate.rstrip("/").rstrip(".html")
                    if candidate_key not in existing:
                        state_links.append(candidate)
                        existing.add(candidate_key)
                        break  # only add one variant per slug

    except (httpx.HTTPError, Exception) as exc:
        logger.warning(
            "Failed to access Legends of America index page: %s. "
            "Falling back to hardcoded slug list.", exc
        )
        state_links = [
            f"{_LOA_BASE}/ghost-towns/{slug}"
            for slug in _LOA_STATE_SLUGS
        ]

    logger.info("Scraping %d Legends of America state page(s).", len(state_links))

    for state_url in state_links:
        if limit is not None and len(records) >= limit:
            break

        try:
            rate_limiter.wait()
            resp = await client.get(state_url, headers=headers)
            if resp.status_code == 404:
                # Try the alternate URL variant (.html suffix or without it)
                alt = _loa_alternate_url(state_url)
                rate_limiter.wait()
                resp = await client.get(alt, headers=headers)
            resp.raise_for_status()
            state_soup = BeautifulSoup(resp.text, "lxml")

            # Target the main content area to avoid nav/sidebar junk.
            # LOA pages typically wrap article content in <article>, <main>,
            # or a div with id/class containing "content" or "entry".
            content_area = (
                state_soup.find("article")
                or state_soup.find("main")
                or state_soup.find(id=re.compile(r"content|entry|article", re.I))
                or state_soup.find(class_=re.compile(r"entry-content|post-content|article-body", re.I))
                or state_soup  # fall back to whole page if no wrapper found
            )

            # Extract ghost town names from list items and paragraphs
            # within the identified content area only.
            for li in content_area.find_all(["li", "p"]):
                # Skip elements that are inside nav, header, footer, or aside
                if li.find_parent(["nav", "header", "footer", "aside"]):
                    continue
                text = li.get_text(strip=True)
                if len(text) > 10 and len(text) < 500:
                    # Try to extract a town name (first bold text or first link)
                    name_tag = li.find(["b", "strong", "a"])
                    if name_tag:
                        town_name = name_tag.get_text(strip=True)
                        # Filter out nav/sidebar junk
                        if (
                            len(town_name) > 2
                            and len(town_name) <= 60
                            and "/" not in town_name
                            and "&" not in town_name
                            and town_name.lower().strip() not in _LOA_JUNK_NAMES
                            and any(c.isalpha() for c in town_name)
                            # Reject strings that look like site navigation
                            and not _LOA_NAV_WORDS_RE.search(town_name)
                        ):
                            records.append({
                                "name": town_name,
                                "description": text[:500],
                                "source": "legends_of_america",
                            })
        except (httpx.HTTPError, Exception) as exc:
            logger.debug("Failed to scrape %s: %s", state_url, exc)
            continue

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

    # US states as (two-letter abbreviation, full name) pairs for ghosttowns.com
    # URL pattern: https://www.ghosttowns.com/states/{abbr}/
    states = [
        ("al", "Alabama"), ("ak", "Alaska"), ("az", "Arizona"), ("ar", "Arkansas"),
        ("ca", "California"), ("co", "Colorado"), ("ct", "Connecticut"), ("de", "Delaware"),
        ("fl", "Florida"), ("ga", "Georgia"), ("id", "Idaho"), ("il", "Illinois"),
        ("in", "Indiana"), ("ia", "Iowa"), ("ks", "Kansas"), ("ky", "Kentucky"),
        ("la", "Louisiana"), ("me", "Maine"), ("md", "Maryland"), ("ma", "Massachusetts"),
        ("mi", "Michigan"), ("mn", "Minnesota"), ("ms", "Mississippi"), ("mo", "Missouri"),
        ("mt", "Montana"), ("ne", "Nebraska"), ("nv", "Nevada"), ("nh", "New Hampshire"),
        ("nj", "New Jersey"), ("nm", "New Mexico"), ("ny", "New York"),
        ("nc", "North Carolina"), ("nd", "North Dakota"), ("oh", "Ohio"),
        ("ok", "Oklahoma"), ("or", "Oregon"), ("pa", "Pennsylvania"),
        ("ri", "Rhode Island"), ("sc", "South Carolina"), ("sd", "South Dakota"),
        ("tn", "Tennessee"), ("tx", "Texas"), ("ut", "Utah"), ("vt", "Vermont"),
        ("va", "Virginia"), ("wa", "Washington"), ("wv", "West Virginia"),
        ("wi", "Wisconsin"), ("wy", "Wyoming"),
    ]

    for state_abbr, state_name in states:
        if limit is not None and len(records) >= limit:
            break

        url = f"{_GT_BASE}/states/{state_abbr}/"
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
                    if f"/{state_abbr}/" in href and text[0].isupper():
                        records.append({
                            "name": text,
                            "description": f"Ghost town in {state_name}",
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
        try:
            zip_bytes = _download_gnis()
            stream = _extract_pipe_file(zip_bytes)
        except Exception as gnis_exc:
            logger.warning(
                "GNIS download/extract failed — skipping GNIS source and continuing "
                "with web scraping sources. Error: %s", gnis_exc,
            )
            completed_sources.add("gnis")
            zip_bytes = None
            stream = None

        if stream is not None:
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
                loa_inserted = 0
                loa_no_coords = 0
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
                            loa_no_coords += 1
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
                                inserted = await insert_location_batch(session, batch)
                                total_inserted += inserted
                                loa_inserted += inserted
                            else:
                                total_inserted += len(batch)
                                loa_inserted += len(batch)
                            batch.clear()
                    if batch:
                        if not dry_run:
                            inserted = await insert_location_batch(session, batch)
                            total_inserted += inserted
                            loa_inserted += inserted
                        else:
                            total_inserted += len(batch)
                            loa_inserted += len(batch)

                logger.info(
                    "Legends of America: %d inserted, %d no coords.",
                    loa_inserted, loa_no_coords,
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
                gt_inserted = 0
                gt_no_coords = 0
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
                            gt_no_coords += 1
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
                                inserted = await insert_location_batch(session, batch)
                                total_inserted += inserted
                                gt_inserted += inserted
                            else:
                                total_inserted += len(batch)
                                gt_inserted += len(batch)
                            batch.clear()
                    if batch:
                        if not dry_run:
                            inserted = await insert_location_batch(session, batch)
                            total_inserted += inserted
                            gt_inserted += inserted
                        else:
                            total_inserted += len(batch)
                            gt_inserted += len(batch)

                logger.info(
                    "Ghosttowns.com: %d inserted, %d no coords.",
                    gt_inserted, gt_no_coords,
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
