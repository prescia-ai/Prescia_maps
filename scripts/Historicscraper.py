#!/usr/bin/env python3
"""
Historic Places, Routes & Features scraper — single source of truth for all
battles, forts, trails, stagecoach routes, railroads, and other historic sites.

Data sources (in priority order):
1. **NRHP CSV** — National Register of Historic Places bulk CSV download
2. **NPS API** — National Park Service battlefields, monuments, historic sites
3. **OpenHistoricalMap** — Overpass API for abandoned railways, historic trails
4. **Wikidata SPARQL** — Battle locations from Wikidata knowledge graph

Replaces data previously scattered across:
- ``load_nrhp.py`` (NRHP ArcGIS API)
- ``load_nps.py`` (NPS API)
- ``load_datasets.py`` (trails, battles, forts, stagecoach stops)
- ``scrape_wikipedia.py`` / ``scrape_wikipedia_2.py`` (battle, trail, fort,
  stagecoach, railroad pages)

Usage::

    # Full import
    python scripts/Historicscraper.py

    # Specific state
    python scripts/Historicscraper.py --state TX

    # Limit records
    python scripts/Historicscraper.py --limit 5000

    # Dry-run
    python scripts/Historicscraper.py --dry-run

    # Skip NPS (no API key needed for NRHP)
    python scripts/Historicscraper.py --skip-nps

    # Skip OpenHistoricalMap
    python scripts/Historicscraper.py --skip-ohm

    # Skip Wikidata SPARQL (enabled by default; use flag to disable)
    python scripts/Historicscraper.py --skip-wikidata
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
import uuid
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import httpx
from shapely.geometry import LineString

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
    insert_linear_feature_batch,
    insert_location_batch,
    load_checkpoint,
    load_existing_linear_feature_names,
    load_existing_names,
    save_checkpoint,
    setup_logging,
)
from app.config import settings  # noqa: E402
from app.models.database import LinearFeature as LinearFeatureModel  # noqa: E402
from app.scrapers.normalizer import clean_name, classify_event_type, is_blocked  # noqa: E402

logger = setup_logging("Historicscraper")

# ---------------------------------------------------------------------------
# NRHP Constants — bulk CSV download from NPS
# ---------------------------------------------------------------------------

NRHP_CSV_URL = (
    "https://irma.nps.gov/DataStore/DownloadFile/719414"
)

# Keywords for filtering NRHP records to metal-detecting relevant sites
NRHP_KEYWORDS: List[str] = [
    "battlefield", "fort", "camp", "post", "mill", "ferry",
    "tavern", "inn", "trading", "stage", "ranch", "homestead", "bridge",
    "crossing", "cemetery", "church", "mission", "depot", "station",
    "school", "jail", "courthouse", "store", "hotel", "saloon",
    "blacksmith", "livery", "armory", "arsenal", "barracks",
]

NRHP_TYPE_MAP: Dict[str, str] = {
    "battlefield": "battle",
    "fort": "structure",
    "camp": "camp",
    "mill": "structure",
    "ferry": "ferry",
    "tavern": "structure",
    "inn": "structure",
    "trading": "trading_post",
    "stage": "stagecoach_stop",
    "ranch": "structure",
    "homestead": "structure",
    "bridge": "structure",
    "crossing": "ferry",
    "cemetery": "cemetery",
    "church": "church",
    "mission": "mission",
    "depot": "railroad_stop",
    "station": "railroad_stop",
    "school": "school",
    "jail": "structure",
    "courthouse": "structure",
    "store": "structure",
    "hotel": "structure",
    "saloon": "structure",
    "blacksmith": "structure",
    "livery": "structure",
    "armory": "structure",
    "arsenal": "structure",
    "barracks": "structure",
}

NRHP_SOURCE = "nrhp"
NRHP_CONFIDENCE = 0.90
# Number of bytes to read when validating that a download looks like CSV text
_NRHP_HEADER_VALIDATION_BYTES = 200

# ---------------------------------------------------------------------------
# NPS Constants
# ---------------------------------------------------------------------------

NPS_API_BASE = "https://developer.nps.gov/api/v1/parks"
NPS_SOURCE = "nps"
NPS_CONFIDENCE = 0.95

DESIGNATION_MAP: Dict[str, str] = {
    "National Battlefield": "battle",
    "National Battlefield Park": "battle",
    "National Battlefield Site": "battle",
    "National Military Park": "battle",
    "National Historic Site": "structure",
    "National Historical Park": "structure",
    "National Monument": "structure",
}

NPS_PAGE_SIZE = 50

# ---------------------------------------------------------------------------
# OpenHistoricalMap Constants
# ---------------------------------------------------------------------------

OHM_OVERPASS_URL = "https://overpass.openhistoricalmap.org/api/interpreter"
OHM_SOURCE = "openhistoricalmap"
OHM_CONFIDENCE = 0.75

# Overpass queries for historic features
_OHM_QUERIES = {
    "abandoned_railway": (
        '[out:json][timeout:120];'
        'area["ISO3166-1"="US"]->.us;'
        '(way["railway"="abandoned"](area.us);'
        'way["railway:historic"](area.us);'
        'way["historic"="railway"](area.us););'
        'out body geom 5000;'
    ),
    "historic_trail": (
        '[out:json][timeout:120];'
        'area["ISO3166-1"="US"]->.us;'
        '(way["historic"="trail"](area.us);'
        'way["historic"="path"](area.us););'
        'out body geom 2000;'
    ),
}

_HEADERS = {
    "User-Agent": (
        "prescia_maps/1.0 (historical research; "
        "https://github.com/prescia-ai/Prescia_maps)"
    )
}

# ---------------------------------------------------------------------------
# Wikidata SPARQL Constants
# ---------------------------------------------------------------------------

WIKIDATA_SPARQL_URL = "https://query.wikidata.org/sparql"
WIKIDATA_SOURCE = "wikidata"
WIKIDATA_CONFIDENCE = 0.88

# SPARQL query: US battles with coordinates
_WIKIDATA_BATTLES_QUERY = """
SELECT ?battle ?battleLabel ?coord ?date WHERE {
  ?battle wdt:P31/wdt:P279* wd:Q178561;
          wdt:P625 ?coord.
  ?battle wdt:P17 wd:Q30.
  OPTIONAL { ?battle wdt:P585 ?date. }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
}
"""

BATCH_SIZE = 500


# ---------------------------------------------------------------------------
# NRHP CSV helpers
# ---------------------------------------------------------------------------

def _download_nrhp_csv(timeout: float = 300.0) -> bytes:
    """Download the NRHP CSV file from NPS Data Store."""
    logger.info("Downloading NRHP CSV from %s …", NRHP_CSV_URL)
    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        response = client.get(NRHP_CSV_URL)
        response.raise_for_status()
    logger.info("Download complete (%.1f MB).", len(response.content) / 1_048_576)
    return response.content


def _extract_nrhp_csv(raw_bytes: bytes) -> Optional[io.TextIOWrapper]:
    """
    Extract the NRHP CSV data.

    The download may be a ZIP archive containing a CSV, or the raw CSV itself.
    Returns None if the content is not valid CSV (e.g. a File Geodatabase).
    """
    # Try as ZIP first
    try:
        with zipfile.ZipFile(io.BytesIO(raw_bytes)) as zf:
            csv_names = [n for n in zf.namelist() if n.lower().endswith(".csv")]
            if csv_names:
                logger.info("Extracting %s from archive.", csv_names[0])
                data = zf.read(csv_names[0])
                return io.TextIOWrapper(io.BytesIO(data), encoding="utf-8-sig", errors="replace")
            # Check for GDB files (not parseable as CSV)
            gdb_names = [n for n in zf.namelist() if ".gdb" in n.lower()]
            if gdb_names:
                logger.error(
                    "NRHP download contains a File Geodatabase (%s), not a CSV. "
                    "The download URL may need updating.", gdb_names[0]
                )
                return None
    except zipfile.BadZipFile:
        pass

    # Check if raw bytes look like CSV (starts with printable ASCII / UTF-8 text)
    header = raw_bytes[:_NRHP_HEADER_VALIDATION_BYTES].decode("utf-8-sig", errors="replace")
    # A valid CSV header will either be all-printable (no newline yet) or contain a newline.
    # Binary/GDB content will fail both checks.
    if header.isprintable() or "\n" in header:
        return io.TextIOWrapper(io.BytesIO(raw_bytes), encoding="utf-8-sig", errors="replace")

    logger.error("NRHP download is not a valid CSV or ZIP file.")
    return None


def _parse_nrhp_csv(
    stream: io.TextIOWrapper,
    state_filter: Optional[str] = None,
    limit: Optional[int] = None,
):
    """
    Yield filtered NRHP records from the CSV stream.

    Each yielded item is a dict with keys matching Location fields.
    Column names are auto-detected from the CSV header (case-insensitive).
    """
    reader = csv.DictReader(stream)
    logger.info("NRHP CSV columns: %s", reader.fieldnames)
    accepted = 0

    # Detect column names (NRHP CSVs use varying headers)
    name_cols = [
        "Resource Name", "RESNAME", "Property Name", "Name",
        "ResourceName", "resource_name", "RESOURCE_NAME",
        "Property_Name", "property_name",
    ]
    lat_cols = ["Latitude", "LATITUDE", "Lat", "lat", "LAT", "Y", "y", "Lat_"]
    lon_cols = ["Longitude", "LONGITUDE", "Lon", "Long", "lon", "LON", "X", "x", "Lon_", "Long_", "LONG"]
    state_cols = ["State", "STATE", "STATE_", "State_Alpha", "STATE_ALPHA", "state", "St"]
    city_cols = ["City", "CITY", "County/Independent City"]
    refnum_cols = ["Reference Number", "NRHP_REFNUM", "Ref#", "RefNum"]

    def _find_col(row: Dict[str, Any], candidates: List[str]) -> str:
        row_lower = {k.lower(): v for k, v in row.items()}
        for c in candidates:
            if c in row:
                return (row[c] or "").strip()
            c_lower = c.lower()
            if c_lower in row_lower:
                return (row_lower[c_lower] or "").strip()
        return ""

    for row in reader:
        name = _find_col(row, name_cols)
        if not name:
            continue

        # State filter
        state = _find_col(row, state_cols)
        if state_filter and state.upper() != state_filter.upper():
            continue

        # Coordinates
        lat_str = _find_col(row, lat_cols)
        lon_str = _find_col(row, lon_cols)
        try:
            lat = float(lat_str)
            lon = float(lon_str)
        except (ValueError, TypeError):
            continue

        if lat == 0.0 and lon == 0.0:
            continue

        # Keyword filter
        if not _nrhp_matches_keywords(name):
            continue

        city = _find_col(row, city_cols)
        ref_num = _find_col(row, refnum_cols)

        desc_parts = []
        if city:
            desc_parts.append(city)
        if state:
            desc_parts.append(state)
        if ref_num:
            desc_parts.append(f"NRHP #{ref_num}")
        description = ", ".join(desc_parts)

        loc_type = _infer_nrhp_type(name)

        yield build_location_record(
            name=name,
            lat=lat,
            lon=lon,
            source=NRHP_SOURCE,
            loc_type=loc_type,
            description=description,
            confidence=NRHP_CONFIDENCE,
        )
        accepted += 1
        if limit is not None and accepted >= limit:
            return


def _nrhp_matches_keywords(name: str) -> bool:
    """Return True if the name contains any NRHP keywords."""
    name_lower = name.lower()
    return any(kw in name_lower for kw in NRHP_KEYWORDS)


def _infer_nrhp_type(name: str) -> str:
    """Infer a LocationType from the NRHP record name."""
    name_lower = name.lower()
    for keyword, loc_type in NRHP_TYPE_MAP.items():
        if keyword in name_lower:
            return loc_type
    return "structure"


# ---------------------------------------------------------------------------
# NPS API helpers
# ---------------------------------------------------------------------------

async def _fetch_nps_parks_page(
    client: httpx.AsyncClient,
    designation: str,
    api_key: str,
    start: int = 0,
) -> Tuple[List[Dict[str, Any]], int]:
    """Fetch one page of parks from the NPS API."""
    params = {
        "designation": designation,
        "limit": NPS_PAGE_SIZE,
        "start": start,
        "api_key": api_key,
        "fields": "fullName,description,latitude,longitude,designation",
    }
    try:
        response = await client.get(NPS_API_BASE, params=params)
        response.raise_for_status()
        data = response.json()
        return data.get("data", []), int(data.get("total", 0))
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        logger.error("NPS API error for %r: %s", designation, exc)
        return [], 0


async def _fetch_all_nps(api_key: str) -> List[Dict[str, Any]]:
    """Fetch all parks across all target designations."""
    all_parks: List[Dict[str, Any]] = []

    async with httpx.AsyncClient(timeout=30.0) as client:
        for designation in DESIGNATION_MAP:
            logger.info("  NPS: fetching designation %r", designation)
            start = 0
            while True:
                parks, total = await _fetch_nps_parks_page(
                    client, designation, api_key, start
                )
                if not parks:
                    break
                for park in parks:
                    park["_designation"] = designation
                all_parks.extend(parks)
                start += len(parks)
                if start >= total:
                    break
            logger.info("  NPS: %d parks for %r", start, designation)

    return all_parks


def _normalise_nps_park(park: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Convert a raw NPS park dict into a Location insert dict."""
    name = (park.get("fullName") or "").strip()
    if not name:
        return None

    try:
        lat = float(park["latitude"])
        lon = float(park["longitude"])
    except (ValueError, TypeError, KeyError):
        return None

    if lat == 0.0 and lon == 0.0:
        return None

    designation = park.get("_designation", park.get("designation", ""))
    loc_type = DESIGNATION_MAP.get(designation, "structure")
    description = (park.get("description") or "")[:1000]

    return build_location_record(
        name=name,
        lat=lat,
        lon=lon,
        source=NPS_SOURCE,
        loc_type=loc_type,
        description=description,
        confidence=NPS_CONFIDENCE,
    )


# ---------------------------------------------------------------------------
# OpenHistoricalMap helpers
# ---------------------------------------------------------------------------

async def _fetch_ohm_features(
    query_name: str,
    query: str,
    rate_limiter: RateLimiter,
) -> List[Dict[str, Any]]:
    """Execute an Overpass query against the OpenHistoricalMap Overpass API and return elements."""
    rate_limiter.wait()
    try:
        async with httpx.AsyncClient(timeout=180.0) as client:
            response = await client.post(
                OHM_OVERPASS_URL,
                data={"data": query},
                headers=_HEADERS,
            )
            response.raise_for_status()
            data = response.json()
            elements = data.get("elements", [])
            logger.info("  OHM: %d elements for %r", len(elements), query_name)
            return elements
    except (httpx.HTTPError, ValueError) as exc:
        logger.error("OHM Overpass error for %r: %s", query_name, exc)
        return []


def _ohm_element_to_linear_feature(
    element: Dict[str, Any],
    feature_type: str,
) -> Optional[Dict[str, Any]]:
    """Convert an Overpass way element to a LinearFeature insert dict."""
    if element.get("type") != "way":
        return None

    geometry = element.get("geometry", [])
    if len(geometry) < 2:
        return None

    coords = [(pt["lon"], pt["lat"]) for pt in geometry]
    tags = element.get("tags", {})
    name = tags.get("name") or tags.get("historic:name") or tags.get("old_name", "")

    if not name:
        return None

    try:
        from geoalchemy2.shape import from_shape
        line = LineString(coords)
        geom = from_shape(line, srid=4326)
    except Exception:
        return None

    return {
        "id": uuid.uuid4(),
        "name": clean_name(name),
        "type": feature_type,
        "geom": geom,
        "source": OHM_SOURCE,
    }


def _ohm_element_to_location(
    element: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Convert an Overpass node/way element to a Location dict if it's a point feature."""
    if element.get("type") == "node":
        lat = element.get("lat")
        lon = element.get("lon")
    elif element.get("type") == "way":
        geometry = element.get("geometry", [])
        if not geometry:
            return None
        # Use centroid of way
        lats = [pt["lat"] for pt in geometry]
        lons = [pt["lon"] for pt in geometry]
        lat = sum(lats) / len(lats)
        lon = sum(lons) / len(lons)
    else:
        return None

    if lat is None or lon is None:
        return None

    tags = element.get("tags", {})
    name = tags.get("name") or tags.get("historic:name") or tags.get("old_name", "")
    if not name:
        return None

    description = tags.get("description", "")
    loc_type = classify_event_type(name, description)

    return build_location_record(
        name=clean_name(name),
        lat=lat,
        lon=lon,
        source=OHM_SOURCE,
        loc_type=loc_type,
        description=description,
        confidence=OHM_CONFIDENCE,
    )


# ---------------------------------------------------------------------------
# Wikidata SPARQL helpers
# ---------------------------------------------------------------------------

import re as _re

_WKT_POINT_RE = _re.compile(
    r"Point\s*\(\s*(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)\s*\)",
    _re.IGNORECASE,
)


def _parse_wkt_point(wkt: str):
    """
    Parse a WKT ``Point(lon lat)`` literal and return ``(lat, lon)`` floats.

    Returns ``None`` if parsing fails.
    """
    m = _WKT_POINT_RE.search(wkt)
    if not m:
        return None
    lon, lat = float(m.group(1)), float(m.group(2))
    return lat, lon


def _parse_wikidata_year(date_str: str) -> Optional[int]:
    """Extract a 4-digit year from a Wikidata date string (e.g. ``2023-07-04T00:00:00Z``)."""
    m = _re.search(r"(\d{4})", date_str)
    return int(m.group(1)) if m else None


async def _fetch_wikidata_battles() -> List[Dict[str, Any]]:
    """
    Query the Wikidata SPARQL endpoint for US battles with coordinates.

    Returns a list of raw SPARQL result bindings.
    """
    headers = {
        **_HEADERS,
        "Accept": "application/sparql-results+json",
    }
    params = {"query": _WIKIDATA_BATTLES_QUERY.strip()}
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.get(
                WIKIDATA_SPARQL_URL,
                params=params,
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()
            bindings = data.get("results", {}).get("bindings", [])
            logger.info("  Wikidata SPARQL: %d bindings returned.", len(bindings))
            return bindings
    except (httpx.HTTPError, ValueError) as exc:
        logger.error("Wikidata SPARQL error: %s", exc)
        return []


def _wikidata_binding_to_location(binding: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Convert a single SPARQL result binding to a Location insert dict."""
    label_val = binding.get("battleLabel", {}).get("value", "")
    name = label_val.strip()
    if not name or name.startswith("Q"):
        # Unlabelled entity — skip
        return None

    coord_val = binding.get("coord", {}).get("value", "")
    parsed = _parse_wkt_point(coord_val)
    if parsed is None:
        return None
    lat, lon = parsed

    year: Optional[int] = None
    date_val = binding.get("date", {}).get("value", "")
    if date_val:
        year = _parse_wikidata_year(date_val)

    return build_location_record(
        name=name,
        lat=lat,
        lon=lon,
        source=WIKIDATA_SOURCE,
        loc_type="battle",
        year=year,
        description="",
        confidence=WIKIDATA_CONFIDENCE,
    )


# ---------------------------------------------------------------------------
# Main async entry point
# ---------------------------------------------------------------------------

async def run(
    state_filter: Optional[str] = None,
    limit: Optional[int] = None,
    dry_run: bool = False,
    skip_nps: bool = False,
    skip_ohm: bool = False,
    skip_wikidata: bool = False,
    checkpoint_path: Optional[Path] = None,
    fresh: bool = False,
) -> None:
    """Import historic places, routes, and features from all sources."""

    engine, session_factory = create_engine_and_session()
    await ensure_tables(engine)

    # -----------------------------------------------------------------------
    # Checkpoint
    # -----------------------------------------------------------------------
    ckpt_path = checkpoint_path or Path("historic_checkpoint.json")
    if fresh and ckpt_path.exists():
        ckpt_path.unlink()
        logger.info("Deleted existing checkpoint (--fresh).")

    ckpt = load_checkpoint(ckpt_path)
    completed_sources = set(ckpt.get("completed_sources", []))
    stats = ckpt.get("stats", {
        "locations_inserted": 0,
        "linear_features_inserted": 0,
        "skipped_dup": 0,
        "skipped_blocked": 0,
    })

    # -----------------------------------------------------------------------
    # Load existing names for dedup
    # -----------------------------------------------------------------------
    logger.info("Loading existing names for dedup …")
    async with session_factory() as session:
        existing_names = await load_existing_names(session)
        existing_lf_names = await load_existing_linear_feature_names(session)
    logger.info("Found %d existing locations, %d linear features.", len(existing_names), len(existing_lf_names))

    dedup = DedupIndex(radius_m=500.0)
    for name in existing_names:
        dedup._names.add(dedup._normalise(name))

    total_locations = stats["locations_inserted"]
    total_linear = stats["linear_features_inserted"]
    skipped_dup = stats["skipped_dup"]
    skipped_blocked = stats["skipped_blocked"]

    # ===================================================================
    # Source 1: NRHP (bulk CSV download)
    # ===================================================================
    if "nrhp" not in completed_sources:
        logger.info("=== Source 1: National Register of Historic Places (CSV) ===")
        raw_bytes = _download_nrhp_csv()
        stream = _extract_nrhp_csv(raw_bytes)

        if stream is None:
            logger.warning(
                "NRHP CSV extraction failed (non-CSV content) — skipping NRHP source."
            )
            completed_sources.add("nrhp")
        else:
            batch: List[Dict[str, Any]] = []
            nrhp_count = 0
            async with session_factory() as session:
                for record in _parse_nrhp_csv(stream, state_filter, limit):
                    nrhp_count += 1
                    cleaned = clean_name(record["name"])
                    if not cleaned:
                        continue

                    if is_blocked(cleaned, record.get("description", "")):
                        skipped_blocked += 1
                        continue

                    if dedup.is_duplicate(cleaned, record["latitude"], record["longitude"]):
                        skipped_dup += 1
                        continue

                    dedup.add(cleaned, record["latitude"], record["longitude"])
                    record["name"] = cleaned
                    batch.append(record)

                    if len(batch) >= BATCH_SIZE:
                        if not dry_run:
                            total_locations += await insert_location_batch(session, batch)
                        else:
                            total_locations += len(batch)
                        batch.clear()

                if batch:
                    if not dry_run:
                        total_locations += await insert_location_batch(session, batch)
                    else:
                        total_locations += len(batch)

            logger.info("NRHP CSV: %d keyword-matched records parsed.", nrhp_count)
            if nrhp_count == 0:
                logger.warning(
                    "NRHP CSV: 0 records matched keywords. "
                    "CSV columns were logged above at INFO level. "
                    "Check column name mapping."
                )
            completed_sources.add("nrhp")
            save_checkpoint(ckpt_path, {
                "completed_sources": list(completed_sources),
                "stats": {
                    "locations_inserted": total_locations,
                    "linear_features_inserted": total_linear,
                    "skipped_dup": skipped_dup,
                    "skipped_blocked": skipped_blocked,
                },
            })
            logger.info("NRHP import complete: %d locations inserted.", total_locations)

    # ===================================================================
    # Source 2: NPS API
    # ===================================================================
    if not skip_nps and "nps" not in completed_sources:
        api_key = settings.NPS_API_KEY
        if not api_key:
            logger.warning(
                "NPS_API_KEY not set — skipping NPS source. "
                "Set it in backend/.env to enable."
            )
        else:
            logger.info("=== Source 2: National Park Service API ===")
            parks = await _fetch_all_nps(api_key)
            logger.info("Fetched %d NPS parks.", len(parks))

            batch = []
            async with session_factory() as session:
                for park in parks:
                    record = _normalise_nps_park(park)
                    if record is None:
                        continue

                    cleaned = clean_name(record["name"])
                    if not cleaned:
                        continue

                    if is_blocked(cleaned, record.get("description", "")):
                        skipped_blocked += 1
                        continue

                    if dedup.is_duplicate(cleaned, record["latitude"], record["longitude"]):
                        skipped_dup += 1
                        continue

                    dedup.add(cleaned, record["latitude"], record["longitude"])
                    record["name"] = cleaned
                    batch.append(record)

                if batch:
                    if not dry_run:
                        total_locations += await insert_location_batch(session, batch)
                    else:
                        total_locations += len(batch)

            completed_sources.add("nps")
            save_checkpoint(ckpt_path, {
                "completed_sources": list(completed_sources),
                "stats": {
                    "locations_inserted": total_locations,
                    "linear_features_inserted": total_linear,
                    "skipped_dup": skipped_dup,
                    "skipped_blocked": skipped_blocked,
                },
            })
            logger.info("NPS import complete: %d total locations.", total_locations)

    # ===================================================================
    # Source 3: OpenHistoricalMap (Overpass API)
    # ===================================================================
    if not skip_ohm and "ohm" not in completed_sources:
        logger.info("=== Source 3: OpenHistoricalMap ===")
        rate_limiter = RateLimiter(min_interval=5.0)

        for query_name, query in _OHM_QUERIES.items():
            logger.info("  Querying OHM for %r …", query_name)
            elements = await _fetch_ohm_features(query_name, query, rate_limiter)

            # Process linear features (ways with 2+ points)
            lf_batch: List[Dict[str, Any]] = []
            loc_batch: List[Dict[str, Any]] = []

            for element in elements:
                if element.get("type") == "way":
                    geometry = element.get("geometry", [])
                    if len(geometry) >= 2:
                        lf_type = "railroad" if "railway" in query_name else "trail"
                        lf_record = _ohm_element_to_linear_feature(element, lf_type)
                        if lf_record and lf_record["name"] not in existing_lf_names:
                            lf_batch.append(lf_record)
                            existing_lf_names.add(lf_record["name"])

                # Also extract point features (nodes and way centroids)
                loc_record = _ohm_element_to_location(element)
                if loc_record:
                    cleaned = clean_name(loc_record["name"])
                    if cleaned and not is_blocked(cleaned, loc_record.get("description", "")):
                        if not dedup.is_duplicate(cleaned, loc_record["latitude"], loc_record["longitude"]):
                            dedup.add(cleaned, loc_record["latitude"], loc_record["longitude"])
                            loc_record["name"] = cleaned
                            loc_batch.append(loc_record)

            # Insert linear features
            if lf_batch and not dry_run:
                async with session_factory() as session:
                    for lf in lf_batch:
                        session.add(LinearFeatureModel(**lf))
                    try:
                        await session.commit()
                        total_linear += len(lf_batch)
                    except Exception as exc:
                        logger.error("Failed to insert linear features: %s", exc)
                        await session.rollback()
            elif dry_run:
                total_linear += len(lf_batch)

            # Insert location points
            if loc_batch:
                async with session_factory() as session:
                    if not dry_run:
                        total_locations += await insert_location_batch(session, loc_batch)
                    else:
                        total_locations += len(loc_batch)

            logger.info(
                "  %s: %d linear features, %d locations.",
                query_name, len(lf_batch), len(loc_batch),
            )

        completed_sources.add("ohm")
        save_checkpoint(ckpt_path, {
            "completed_sources": list(completed_sources),
            "stats": {
                "locations_inserted": total_locations,
                "linear_features_inserted": total_linear,
                "skipped_dup": skipped_dup,
                "skipped_blocked": skipped_blocked,
            },
        })

    # ===================================================================
    # Source 4: Wikidata SPARQL (US battles)
    # ===================================================================
    if not skip_wikidata and "wikidata" not in completed_sources:
        logger.info("=== Source 4: Wikidata SPARQL (US battles) ===")
        bindings = await _fetch_wikidata_battles()
        logger.info("Fetched %d Wikidata battle bindings.", len(bindings))

        batch = []
        async with session_factory() as session:
            for binding in bindings:
                record = _wikidata_binding_to_location(binding)
                if record is None:
                    continue

                cleaned = clean_name(record["name"])
                if not cleaned:
                    continue

                if is_blocked(cleaned, record.get("description", "")):
                    skipped_blocked += 1
                    continue

                if dedup.is_duplicate(cleaned, record["latitude"], record["longitude"]):
                    skipped_dup += 1
                    continue

                dedup.add(cleaned, record["latitude"], record["longitude"])
                record["name"] = cleaned
                batch.append(record)

            if batch:
                if not dry_run:
                    total_locations += await insert_location_batch(session, batch)
                else:
                    total_locations += len(batch)

        completed_sources.add("wikidata")
        save_checkpoint(ckpt_path, {
            "completed_sources": list(completed_sources),
            "stats": {
                "locations_inserted": total_locations,
                "linear_features_inserted": total_linear,
                "skipped_dup": skipped_dup,
                "skipped_blocked": skipped_blocked,
            },
        })
        logger.info("Wikidata import complete: %d new locations.", len(batch))

    await engine.dispose()

    # Clean up checkpoint on success
    if ckpt_path.exists() and not dry_run:
        ckpt_path.unlink()

    label = "[DRY-RUN] " if dry_run else ""
    logger.info(
        "%sDone. Locations: %d | Linear features: %d | Duplicates: %d | Blocked: %d",
        label, total_locations, total_linear, skipped_dup, skipped_blocked,
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import historic places, routes & features into Prescia Maps."
    )
    parser.add_argument(
        "--state", metavar="XX", default=None,
        help="Two-letter state abbreviation for NRHP filter (e.g. TX).",
    )
    parser.add_argument(
        "--limit", type=int, default=None, metavar="N",
        help="Maximum number of NRHP records to import.",
    )
    parser.add_argument(
        "--dry-run", action="store_true", default=False,
        help="Fetch and parse records but do not write to the database.",
    )
    parser.add_argument(
        "--skip-nps", action="store_true", default=False,
        help="Skip the NPS API source (useful if NPS_API_KEY is not set).",
    )
    parser.add_argument(
        "--skip-ohm", action="store_true", default=False,
        help="Skip the OpenHistoricalMap source.",
    )
    parser.add_argument(
        "--skip-wikidata", action="store_true", default=False,
        help="Skip the Wikidata SPARQL battle source.",
    )
    parser.add_argument(
        "--checkpoint", default="historic_checkpoint.json", metavar="PATH",
        help="Checkpoint file path (default: historic_checkpoint.json).",
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
            skip_nps=args.skip_nps,
            skip_ohm=args.skip_ohm,
            skip_wikidata=args.skip_wikidata,
            checkpoint_path=Path(args.checkpoint),
            fresh=args.fresh,
        )
    )


if __name__ == "__main__":
    main()
