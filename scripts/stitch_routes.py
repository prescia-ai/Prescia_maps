#!/usr/bin/env python3
"""
Route stitcher — builds LinearFeature records from clustered point locations.

For routes that lack explicit geometry data (stagecoach stops, railroad stations,
pony express stations, trail waypoints), this script:

1. Downloads actual polyline geometry for National Historic Trails from the
   NPS ArcGIS open-data portal and inserts them as ``LinearFeature`` records.

2. Groups related ``Location`` records by route-name pattern, orders the stops
   geographically using nearest-neighbour traversal (west-to-east), and inserts
   a ``LinearFeature`` LINESTRING connecting them.

Running this after the main scrapers means every major named route will appear
as a **line** on the map, with its individual stops rendered as **dots**.

Usage::

    # Preview what would be created (no DB writes)
    python scripts/stitch_routes.py --dry-run

    # Full run
    python scripts/stitch_routes.py

    # Require at least 5 stops to form a route
    python scripts/stitch_routes.py --min-points 5

    # Skip the NPS National Trails download
    python scripts/stitch_routes.py --skip-nps-trails

    # Start fresh (delete checkpoint)
    python scripts/stitch_routes.py --fresh
"""

from __future__ import annotations

import argparse
import asyncio
import math
import sys
import uuid
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import httpx
from shapely.geometry import LineString

# ---------------------------------------------------------------------------
# Bootstrap: add backend to sys.path so app.* imports work
# ---------------------------------------------------------------------------
_SCRIPT_DIR = Path(__file__).resolve().parent
_BACKEND_DIR = _SCRIPT_DIR.parent / "backend"
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from scraper_utils import (  # noqa: E402
    create_engine_and_session,
    ensure_tables,
    insert_linear_feature_batch,
    load_checkpoint,
    load_existing_linear_feature_names,
    save_checkpoint,
    setup_logging,
)
from app.models.database import LinearFeature as LinearFeatureModel, Location  # noqa: E402
from app.scrapers.normalizer import clean_name  # noqa: E402
from sqlalchemy import select  # noqa: E402

logger = setup_logging("stitch_routes")

# ---------------------------------------------------------------------------
# NPS National Trails System — ArcGIS REST endpoint
# ---------------------------------------------------------------------------

NPS_TRAILS_URL = (
    "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services/"
    "National_Trails_System/FeatureServer/0/query"
)
NPS_TRAILS_SOURCE = "nps_trails"
NPS_TRAILS_PAGE_SIZE = 200

_HEADERS = {
    "User-Agent": (
        "prescia_maps/1.0 (historical research; "
        "https://github.com/prescia-ai/Prescia_maps)"
    )
}

# ---------------------------------------------------------------------------
# Explicit route-stitching patterns
#
# Each entry defines a named route to build from existing Location records:
#   route_name      — name of the LinearFeature to create
#   feature_type    — LinearFeatureType value ("trail", "road", "railroad")
#   location_type   — LocationType value to query (e.g. "pony_express")
#   name_patterns   — substrings that must appear in Location.name (case-insensitive)
#                     Empty list = include ALL records of that location_type
# ---------------------------------------------------------------------------

STITCH_PATTERNS: List[Dict[str, Any]] = [
    # ── Pony Express ────────────────────────────────────────────────────────
    {
        "route_name": "Pony Express Route",
        "feature_type": "trail",
        "location_type": "pony_express",
        "name_patterns": [],  # all pony_express records
    },
    # ── Stagecoach routes ───────────────────────────────────────────────────
    {
        "route_name": "Butterfield Overland Mail Route",
        "feature_type": "road",
        "location_type": "stagecoach_stop",
        "name_patterns": ["butterfield", "overland mail", "overland stage"],
    },
    {
        "route_name": "Central Overland Route",
        "feature_type": "road",
        "location_type": "stagecoach_stop",
        "name_patterns": ["central overland", "ben holladay", "holladay"],
    },
    # ── Historic trails ─────────────────────────────────────────────────────
    {
        "route_name": "Oregon Trail",
        "feature_type": "trail",
        "location_type": "trail",
        "name_patterns": ["oregon trail"],
    },
    {
        "route_name": "Santa Fe Trail",
        "feature_type": "trail",
        "location_type": "trail",
        "name_patterns": ["santa fe trail"],
    },
    {
        "route_name": "Mormon Trail",
        "feature_type": "trail",
        "location_type": "trail",
        "name_patterns": ["mormon trail", "pioneer trail"],
    },
    {
        "route_name": "California Trail",
        "feature_type": "trail",
        "location_type": "trail",
        "name_patterns": ["california trail"],
    },
    {
        "route_name": "Lewis and Clark Trail",
        "feature_type": "trail",
        "location_type": "trail",
        "name_patterns": ["lewis and clark", "lewis & clark"],
    },
    # ── Railroads ───────────────────────────────────────────────────────────
    {
        "route_name": "Union Pacific Railroad",
        "feature_type": "railroad",
        "location_type": "railroad_stop",
        "name_patterns": ["union pacific"],
    },
    {
        "route_name": "Central Pacific Railroad",
        "feature_type": "railroad",
        "location_type": "railroad_stop",
        "name_patterns": ["central pacific"],
    },
    {
        "route_name": "Denver & Rio Grande Railroad",
        "feature_type": "railroad",
        "location_type": "railroad_stop",
        "name_patterns": ["denver", "rio grande", "d&rg", "d&rgw"],
    },
    {
        "route_name": "Atchison, Topeka & Santa Fe Railroad",
        "feature_type": "railroad",
        "location_type": "railroad_stop",
        "name_patterns": ["santa fe railroad", "atsf", "atchison", "topeka"],
    },
    {
        "route_name": "Southern Pacific Railroad",
        "feature_type": "railroad",
        "location_type": "railroad_stop",
        "name_patterns": ["southern pacific"],
    },
    {
        "route_name": "Northern Pacific Railroad",
        "feature_type": "railroad",
        "location_type": "railroad_stop",
        "name_patterns": ["northern pacific"],
    },
]

MIN_POINTS_DEFAULT = 3

# Auto-grouping thresholds for _extract_route_prefix / _auto_group_locations
# A prefix must be at least this many characters long to avoid grouping
# unrelated single-word records (e.g. "Mill") into spurious micro-routes.
_MIN_PREFIX_LENGTH = 6
# Cap the prefix at this many words so we don't over-specify routes
# (e.g. "Atchison Topeka Santa Fe Rail" would be too narrow).
_MAX_PREFIX_WORDS = 4

# ---------------------------------------------------------------------------
# NPS National Trails geometry helpers
# ---------------------------------------------------------------------------


async def _fetch_nps_trails_page(
    client: httpx.AsyncClient,
    offset: int = 0,
    page_size: int = NPS_TRAILS_PAGE_SIZE,
) -> Tuple[List[Dict[str, Any]], bool]:
    """Fetch one page of National Trails System features from the ArcGIS REST API."""
    params = {
        "where": "1=1",
        "outFields": "TRAIL_NAME,DESIGNATED_NAME,TRAIL_TYPE,ADMIN_ORG",
        "returnGeometry": "true",
        "geometryType": "esriGeometryPolyline",
        "outSR": "4326",
        "f": "geojson",
        "resultOffset": offset,
        "resultRecordCount": page_size,
    }
    try:
        response = await client.get(NPS_TRAILS_URL, params=params, headers=_HEADERS)
        response.raise_for_status()
        data = response.json()
        features = data.get("features", [])
        exceeded = data.get("exceededTransferLimit", False)
        return features, exceeded
    except (httpx.HTTPError, ValueError) as exc:
        logger.error("NPS Trails API error at offset %d: %s", offset, exc)
        return [], False


async def _fetch_all_nps_trails() -> List[Dict[str, Any]]:
    """Fetch all National Trails System features with polyline geometry."""
    all_features: List[Dict[str, Any]] = []
    offset = 0
    async with httpx.AsyncClient(timeout=120.0) as client:
        while True:
            features, exceeded = await _fetch_nps_trails_page(client, offset)
            all_features.extend(features)
            logger.info(
                "  NPS Trails: received %d features (offset=%d, total so far=%d)",
                len(features), offset, len(all_features),
            )
            if not features or not exceeded:
                break
            offset += len(features)

    logger.info("NPS Trails: %d total features fetched.", len(all_features))
    return all_features


def _nps_feature_to_linear_feature(
    feature: Dict[str, Any],
    existing_names: Set[str],
) -> Optional[Dict[str, Any]]:
    """Convert a GeoJSON feature from NPS Trails into a LinearFeature insert dict."""
    from geoalchemy2.shape import from_shape  # local import — heavy dep

    props = feature.get("properties") or {}
    name = (
        props.get("DESIGNATED_NAME")
        or props.get("TRAIL_NAME")
        or ""
    ).strip()
    if not name:
        return None

    cleaned_name = clean_name(name)
    if not cleaned_name:
        return None

    # Skip if already stored
    if cleaned_name.lower() in {n.lower() for n in existing_names}:
        return None

    geometry = feature.get("geometry") or {}
    geom_type = geometry.get("type", "")
    coords_data = geometry.get("coordinates") or []
    if not coords_data:
        return None

    # Determine linear feature type
    feature_type = "trail"
    name_lower = cleaned_name.lower()
    if "railroad" in name_lower or "railway" in name_lower:
        feature_type = "railroad"
    elif "road" in name_lower or "highway" in name_lower:
        feature_type = "road"

    # Build shapely geometry
    try:
        if geom_type == "LineString":
            if len(coords_data) < 2:
                return None
            line = LineString([(c[0], c[1]) for c in coords_data])
        elif geom_type == "MultiLineString":
            # Use the longest individual segment to avoid a zig-zag line
            segments = [seg for seg in coords_data if len(seg) >= 2]
            if not segments:
                return None
            longest = max(segments, key=len)
            line = LineString([(c[0], c[1]) for c in longest])
        else:
            return None

        geom = from_shape(line, srid=4326)
    except Exception as exc:
        logger.warning("Failed to build geometry for NPS trail %r: %s", cleaned_name, exc)
        return None

    return {
        "id": uuid.uuid4(),
        "name": cleaned_name,
        "type": feature_type,
        "geom": geom,
        "source": NPS_TRAILS_SOURCE,
    }


# ---------------------------------------------------------------------------
# Geographic ordering — nearest-neighbour traversal
# ---------------------------------------------------------------------------


def _nearest_neighbor_order(
    points: List[Tuple[float, float]],
) -> List[Tuple[float, float]]:
    """
    Order ``(lat, lon)`` points using nearest-neighbour traversal.

    Starts at the westernmost point (lowest longitude) and greedily visits
    the closest unvisited point at each step.  This produces a sensible path
    for most US routes without requiring knowledge of the actual route geometry.
    """
    if len(points) <= 2:
        return list(points)

    def _sq_dist(a: Tuple[float, float], b: Tuple[float, float]) -> float:
        """Squared approximate planar distance (no sqrt needed for comparison)."""
        dlat = a[0] - b[0]
        dlon = (a[1] - b[1]) * math.cos(math.radians((a[0] + b[0]) / 2.0))
        return dlat * dlat + dlon * dlon

    remaining = list(points)
    # Start from the westernmost point (minimum longitude)
    start_idx = min(range(len(remaining)), key=lambda i: remaining[i][1])
    ordered = [remaining.pop(start_idx)]

    while remaining:
        last = ordered[-1]
        nearest_idx = min(range(len(remaining)), key=lambda i: _sq_dist(last, remaining[i]))
        ordered.append(remaining.pop(nearest_idx))

    return ordered


# ---------------------------------------------------------------------------
# Location query helpers
# ---------------------------------------------------------------------------


async def _load_stops_for_pattern(
    session: Any,
    location_type: str,
    name_patterns: List[str],
) -> List[Tuple[str, float, float]]:
    """
    Query ``Location`` records matching ``location_type`` and ``name_patterns``.

    Returns a list of ``(name, lat, lon)`` tuples.
    """
    from app.models.database import LocationType as LT

    try:
        lt_val = LT(location_type)
    except ValueError:
        logger.warning("Unknown location type: %r — skipping.", location_type)
        return []

    stmt = (
        select(Location.name, Location.latitude, Location.longitude)
        .where(
            Location.type == lt_val,
            Location.latitude.isnot(None),
            Location.longitude.isnot(None),
        )
    )
    result = await session.execute(stmt)
    rows = result.fetchall()

    if not name_patterns:
        return [(r[0], r[1], r[2]) for r in rows]

    # Filter by name patterns (any match)
    matched = []
    for name, lat, lon in rows:
        name_lower = (name or "").lower()
        if any(pat.lower() in name_lower for pat in name_patterns):
            matched.append((name, lat, lon))
    return matched


# ---------------------------------------------------------------------------
# LinearFeature builder
# ---------------------------------------------------------------------------


def _build_linear_feature(
    route_name: str,
    feature_type: str,
    ordered_points: List[Tuple[float, float]],
    source: str = "stitch_routes",
) -> Optional[Dict[str, Any]]:
    """Build a LinearFeature insert dict from ordered ``(lat, lon)`` points."""
    from geoalchemy2.shape import from_shape  # local import

    if len(ordered_points) < 2:
        return None

    try:
        # LineString takes (lon, lat) coordinate pairs
        coords = [(lon, lat) for lat, lon in ordered_points]
        line = LineString(coords)
        geom = from_shape(line, srid=4326)
    except Exception as exc:
        logger.warning("Failed to build geometry for %r: %s", route_name, exc)
        return None

    return {
        "id": uuid.uuid4(),
        "name": route_name,
        "type": feature_type,
        "geom": geom,
        "source": source,
    }


# ---------------------------------------------------------------------------
# Auto-grouping catch-all: discover routes not listed in STITCH_PATTERNS
# ---------------------------------------------------------------------------

_STOP_SUFFIXES = (
    " station", " stop", " relay", " depot", " crossing",
    " camp", " ranch", " ford", " ferry", " junction",
)


def _extract_route_prefix(name: str) -> str:
    """
    Heuristically extract a route prefix from a stop name.

    Examples::

        "Wells Fargo Station - Tucson"  →  "Wells Fargo"
        "Butterfield Stage Stop"        →  "Butterfield"
        "Denver and Rio Grande Depot"   →  "Denver and Rio Grande"
    """
    prefix = name.lower()
    # Strip trailing suffixes
    for suffix in _STOP_SUFFIXES:
        if prefix.endswith(suffix):
            prefix = prefix[: -len(suffix)].strip()
            break
    # Strip "- <city>" patterns
    if " - " in prefix:
        prefix = prefix[: prefix.index(" - ")].strip()
    # Keep at most _MAX_PREFIX_WORDS words to avoid over-specific prefixes
    words = prefix.split()
    if len(words) > _MAX_PREFIX_WORDS:
        prefix = " ".join(words[:_MAX_PREFIX_WORDS])
    return prefix


async def _auto_group_locations(
    session: Any,
    location_type: str,
    existing_route_names: Set[str],
    min_points: int,
) -> List[Dict[str, Any]]:
    """
    Discover additional routes not listed in STITCH_PATTERNS by grouping
    Location records of the given type by shared name prefix.

    Only groups with ``min_points`` or more stops and a prefix of at least
    ``_MIN_PREFIX_LENGTH`` characters are considered, to avoid spurious
    micro-routes.
    """
    from app.models.database import LocationType as LT

    try:
        lt_val = LT(location_type)
    except ValueError:
        return []

    stmt = (
        select(Location.name, Location.latitude, Location.longitude)
        .where(
            Location.type == lt_val,
            Location.latitude.isnot(None),
            Location.longitude.isnot(None),
        )
    )
    result = await session.execute(stmt)
    rows = result.fetchall()
    if not rows:
        return []

    # Group by prefix
    groups: Dict[str, List[Tuple[float, float]]] = defaultdict(list)
    for name, lat, lon in rows:
        if not name:
            continue
        prefix = _extract_route_prefix(name)
        if len(prefix) >= _MIN_PREFIX_LENGTH:
            groups[prefix].append((lat, lon))

    feature_type_map = {
        "stagecoach_stop": "road",
        "railroad_stop": "railroad",
        "trail": "trail",
        "pony_express": "trail",
    }
    feature_type = feature_type_map.get(location_type, "road")

    records: List[Dict[str, Any]] = []
    for prefix, points in groups.items():
        if len(points) < min_points:
            continue

        route_name = prefix.title()

        # Skip if a similar name already exists
        route_lower = route_name.lower()
        if any(
            route_lower in ex.lower() or ex.lower() in route_lower
            for ex in existing_route_names
        ):
            continue

        ordered = _nearest_neighbor_order(points)
        record = _build_linear_feature(
            route_name=route_name,
            feature_type=feature_type,
            ordered_points=ordered,
        )
        if record:
            records.append(record)
            existing_route_names.add(route_name)
            logger.info(
                "  [AUTO] %r: %d stops → route (%s).",
                route_name, len(points), feature_type,
            )

    return records


# ---------------------------------------------------------------------------
# Main async entry point
# ---------------------------------------------------------------------------


async def run(
    dry_run: bool = False,
    min_points: int = MIN_POINTS_DEFAULT,
    skip_nps_trails: bool = False,
    checkpoint_path: Optional[Path] = None,
    fresh: bool = False,
) -> None:
    """Download NPS trail geometry and stitch point clusters into route lines."""

    engine, session_factory = create_engine_and_session()
    await ensure_tables(engine)

    # -----------------------------------------------------------------------
    # Checkpoint
    # -----------------------------------------------------------------------
    ckpt_path = checkpoint_path or Path("stitch_routes_checkpoint.json")
    if fresh and ckpt_path.exists():
        ckpt_path.unlink()
        logger.info("Deleted existing checkpoint (--fresh).")

    ckpt = load_checkpoint(ckpt_path)
    completed_sources: Set[str] = set(ckpt.get("completed_sources", []))
    stats: Dict[str, int] = ckpt.get(
        "stats",
        {"routes_created": 0, "routes_skipped": 0, "nps_trails_inserted": 0},
    )

    routes_created: int = stats["routes_created"]
    routes_skipped: int = stats["routes_skipped"]
    nps_trails_inserted: int = stats["nps_trails_inserted"]

    # -----------------------------------------------------------------------
    # Load existing linear feature names (dedup guard)
    # -----------------------------------------------------------------------
    logger.info("Loading existing linear feature names …")
    async with session_factory() as session:
        existing_lf_names: Set[str] = await load_existing_linear_feature_names(session)
    logger.info("Found %d existing linear features.", len(existing_lf_names))

    # =======================================================================
    # Source 1: NPS National Trails System (ArcGIS REST → GeoJSON)
    # =======================================================================
    if not skip_nps_trails and "nps_trails" not in completed_sources:
        logger.info("=== Source 1: NPS National Trails System (ArcGIS REST) ===")
        features = await _fetch_all_nps_trails()

        lf_batch: List[Dict[str, Any]] = []
        for feat in features:
            record = _nps_feature_to_linear_feature(feat, existing_lf_names)
            if record:
                lf_batch.append(record)
                existing_lf_names.add(record["name"])

        logger.info("NPS Trails: %d new linear features to insert.", len(lf_batch))

        if lf_batch:
            if dry_run:
                nps_trails_inserted += len(lf_batch)
                for rec in lf_batch[:20]:
                    logger.info("  [DRY-RUN] Would insert: %r (%s)", rec["name"], rec["type"])
                if len(lf_batch) > 20:
                    logger.info("  [DRY-RUN] … and %d more.", len(lf_batch) - 20)
            else:
                async with session_factory() as session:
                    for lf in lf_batch:
                        session.add(LinearFeatureModel(**lf))
                    try:
                        await session.commit()
                        nps_trails_inserted += len(lf_batch)
                        logger.info("Inserted %d NPS trail linear features.", len(lf_batch))
                    except Exception as exc:
                        logger.error("Failed to insert NPS trail features: %s", exc)
                        await session.rollback()

        completed_sources.add("nps_trails")
        save_checkpoint(
            ckpt_path,
            {
                "completed_sources": list(completed_sources),
                "stats": {
                    "routes_created": routes_created,
                    "routes_skipped": routes_skipped,
                    "nps_trails_inserted": nps_trails_inserted,
                },
            },
        )

    # =======================================================================
    # Source 2: Route stitching from existing Location points
    # =======================================================================
    if "stitch" not in completed_sources:
        logger.info("=== Source 2: Route stitching from point clusters ===")

        lf_batch = []
        async with session_factory() as session:
            # -- Explicit patterns from STITCH_PATTERNS -------------------
            for pattern in STITCH_PATTERNS:
                route_name: str = pattern["route_name"]
                feature_type: str = pattern["feature_type"]
                location_type: str = pattern["location_type"]
                name_patterns: List[str] = pattern["name_patterns"]

                # Skip if a LinearFeature with this name already exists
                if route_name in existing_lf_names:
                    logger.info("  [SKIP] %r already exists.", route_name)
                    routes_skipped += 1
                    continue

                stops = await _load_stops_for_pattern(session, location_type, name_patterns)

                if len(stops) < min_points:
                    logger.info(
                        "  [SKIP] %r: only %d stop(s) found (need ≥ %d).",
                        route_name, len(stops), min_points,
                    )
                    routes_skipped += 1
                    continue

                points = [(lat, lon) for _, lat, lon in stops]
                ordered = _nearest_neighbor_order(points)

                record = _build_linear_feature(
                    route_name=route_name,
                    feature_type=feature_type,
                    ordered_points=ordered,
                )
                if record:
                    lf_batch.append(record)
                    existing_lf_names.add(route_name)
                    logger.info(
                        "  [STITCH] %r: %d stop(s) → LINESTRING (%s).",
                        route_name, len(stops), feature_type,
                    )

            # -- Auto-discover additional routes (catch-all) --------------
            for loc_type in ("stagecoach_stop", "railroad_stop", "pony_express"):
                auto_records = await _auto_group_locations(
                    session, loc_type, existing_lf_names, min_points
                )
                lf_batch.extend(auto_records)

        logger.info("Route stitching: %d route(s) to insert.", len(lf_batch))

        if lf_batch:
            if dry_run:
                routes_created += len(lf_batch)
                for rec in lf_batch:
                    logger.info(
                        "  [DRY-RUN] Would insert: %r (type=%s)", rec["name"], rec["type"]
                    )
            else:
                async with session_factory() as session:
                    for lf in lf_batch:
                        session.add(LinearFeatureModel(**lf))
                    try:
                        await session.commit()
                        routes_created += len(lf_batch)
                        logger.info(
                            "Inserted %d stitched route linear features.", len(lf_batch)
                        )
                    except Exception as exc:
                        logger.error("Failed to insert stitched routes: %s", exc)
                        await session.rollback()

        completed_sources.add("stitch")
        save_checkpoint(
            ckpt_path,
            {
                "completed_sources": list(completed_sources),
                "stats": {
                    "routes_created": routes_created,
                    "routes_skipped": routes_skipped,
                    "nps_trails_inserted": nps_trails_inserted,
                },
            },
        )

    await engine.dispose()

    # Remove checkpoint on clean exit (not on dry-run — nothing was written)
    if ckpt_path.exists() and not dry_run:
        ckpt_path.unlink()

    label = "[DRY-RUN] " if dry_run else ""
    logger.info(
        "%sDone.  NPS trails: %d | Stitched routes: %d | Skipped patterns: %d",
        label,
        nps_trails_inserted,
        routes_created,
        routes_skipped,
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Build LinearFeature lines from NPS trail geometry and clustered "
            "point-stop records (stagecoach stops, railroad stations, trail "
            "waypoints, pony express stations)."
        )
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Preview what would be created without writing to the database.",
    )
    parser.add_argument(
        "--min-points",
        type=int,
        default=MIN_POINTS_DEFAULT,
        metavar="N",
        help=(
            f"Minimum number of stops required to stitch a route "
            f"(default: {MIN_POINTS_DEFAULT})."
        ),
    )
    parser.add_argument(
        "--skip-nps-trails",
        action="store_true",
        default=False,
        help="Skip downloading National Trails System geometry from NPS ArcGIS.",
    )
    parser.add_argument(
        "--checkpoint",
        default="stitch_routes_checkpoint.json",
        metavar="PATH",
        help="Checkpoint file path (default: stitch_routes_checkpoint.json).",
    )
    parser.add_argument(
        "--fresh",
        action="store_true",
        default=False,
        help="Delete the existing checkpoint and start from scratch.",
    )
    args = parser.parse_args()

    asyncio.run(
        run(
            dry_run=args.dry_run,
            min_points=args.min_points,
            skip_nps_trails=args.skip_nps_trails,
            checkpoint_path=Path(args.checkpoint),
            fresh=args.fresh,
        )
    )


if __name__ == "__main__":
    main()
