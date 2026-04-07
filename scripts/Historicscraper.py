#!/usr/bin/env python3
"""
Historic Places, Routes & Features scraper — single source of truth for all
battles, forts, trails, stagecoach routes, railroads, and other historic sites.

Data sources (in priority order):
1. **NRHP CSV** — National Register of Historic Places bulk data
2. **NPS API** — National Park Service battlefields, monuments, historic sites
3. **OpenHistoricalMap** — Overpass API for abandoned railways, historic trails

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
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import uuid
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
# NRHP Constants
# ---------------------------------------------------------------------------

NRHP_API_URL = (
    "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services"
    "/NRHP_Listings/FeatureServer/0/query"
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
NRHP_PAGE_SIZE = 1000

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

OHM_OVERPASS_URL = "https://overpass-api.de/api/interpreter"
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

BATCH_SIZE = 500


# ---------------------------------------------------------------------------
# NRHP API helpers
# ---------------------------------------------------------------------------

async def _fetch_nrhp_page(
    client: httpx.AsyncClient,
    state: Optional[str],
    offset: int,
) -> List[Dict[str, Any]]:
    """Fetch one page of NRHP records from the ArcGIS REST service."""
    where = f"STATE_='{state.upper()}'" if state else "1=1"
    params = {
        "where": where,
        "outFields": "RESNAME,CITY,STATE_,LATITUDE,LONGITUDE,NRHP_REFNUM",
        "f": "json",
        "resultRecordCount": NRHP_PAGE_SIZE,
        "resultOffset": offset,
    }
    try:
        response = await client.get(NRHP_API_URL, params=params, headers=_HEADERS)
        response.raise_for_status()
        data = response.json()
        features = data.get("features", [])
        return [f.get("attributes", {}) for f in features]
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        logger.error("NRHP API error at offset %d: %s", offset, exc)
        return []


async def _fetch_all_nrhp(
    state: Optional[str],
    limit: Optional[int],
    timeout: float = 30.0,
) -> List[Dict[str, Any]]:
    """Paginate through the NRHP API and return all matching records."""
    all_records: List[Dict[str, Any]] = []
    offset = 0

    async with httpx.AsyncClient(timeout=timeout) as client:
        while True:
            page = await _fetch_nrhp_page(client, state, offset)
            if not page:
                break
            all_records.extend(page)
            logger.info("  NRHP: fetched %d records (total: %d)", len(page), len(all_records))
            offset += len(page)

            if len(page) < NRHP_PAGE_SIZE:
                break
            if limit is not None and len(all_records) >= limit:
                all_records = all_records[:limit]
                break

    return all_records


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


def _normalise_nrhp_record(attrs: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Convert raw NRHP attributes into a Location insert dict."""
    name = (attrs.get("RESNAME") or "").strip()
    if not name:
        return None

    try:
        lat = float(attrs["LATITUDE"])
        lon = float(attrs["LONGITUDE"])
    except (ValueError, TypeError, KeyError):
        return None

    if lat == 0.0 and lon == 0.0:
        return None

    city = (attrs.get("CITY") or "").strip()
    state = (attrs.get("STATE_") or "").strip()
    ref_num = (attrs.get("NRHP_REFNUM") or "").strip()

    desc_parts = []
    if city:
        desc_parts.append(city)
    if state:
        desc_parts.append(state)
    if ref_num:
        desc_parts.append(f"NRHP #{ref_num}")
    description = ", ".join(desc_parts)

    loc_type = _infer_nrhp_type(name)

    return build_location_record(
        name=name,
        lat=lat,
        lon=lon,
        source=NRHP_SOURCE,
        loc_type=loc_type,
        description=description,
        confidence=NRHP_CONFIDENCE,
    )


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
    """Execute an Overpass query against the main Overpass API and return elements."""
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
# Main async entry point
# ---------------------------------------------------------------------------

async def run(
    state_filter: Optional[str] = None,
    limit: Optional[int] = None,
    dry_run: bool = False,
    skip_nps: bool = False,
    skip_ohm: bool = False,
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
    # Source 1: NRHP (ArcGIS REST API)
    # ===================================================================
    if "nrhp" not in completed_sources:
        logger.info("=== Source 1: National Register of Historic Places ===")
        raw_records = await _fetch_all_nrhp(state_filter, limit)
        logger.info("Fetched %d raw NRHP records.", len(raw_records))

        # Filter by keywords
        filtered = [
            r for r in raw_records
            if _nrhp_matches_keywords(r.get("RESNAME", ""))
        ]
        logger.info("%d records match keyword filter.", len(filtered))

        batch: List[Dict[str, Any]] = []
        async with session_factory() as session:
            for attrs in filtered:
                record = _normalise_nrhp_record(attrs)
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
            checkpoint_path=Path(args.checkpoint),
            fresh=args.fresh,
        )
    )


if __name__ == "__main__":
    main()
