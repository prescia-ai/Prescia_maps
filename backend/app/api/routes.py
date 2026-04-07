"""
All API route handlers for the Prescia Maps backend.

Endpoints
---------
GET /health                 – liveness/readiness probe
GET /locations              – all point locations as GeoJSON FeatureCollection
GET /features               – all linear features as GeoJSON FeatureCollection
GET /heatmap                – weighted density array for heatmap overlay
GET /score?lat=&lon=        – interest score for a given coordinate
POST /locations             – insert a new historical location
POST /scrape                – trigger a fresh Wikipedia scrape (admin)
GET /blm-lands              – BLM public land boundaries within radius
GET /blm-lands/tile-url     – BLM tile service URL for direct map rendering
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from geoalchemy2 import Geography
from geoalchemy2.functions import ST_Buffer, ST_DWithin, ST_MakePoint, ST_SetSRID
from sqlalchemy import cast, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.database import LinearFeature, Location, get_db
from app.models.schemas import (
    GeoJSONFeatureCollection,
    HealthResponse,
    HeatmapPoint,
    HotspotCluster,
    LocationCreate,
    LocationResponse,
    ScoreResponse,
)
from app.scoring.engine import compute_heatmap_data, score_location

logger = logging.getLogger(__name__)

router = APIRouter()

# ---------------------------------------------------------------------------
# BLM in-memory cache
# ---------------------------------------------------------------------------

# Simple dict cache: key -> (timestamp, data)
_BLM_CACHE: Dict[str, Tuple[float, Any]] = {}
_BLM_CACHE_TTL = 3600.0  # 1 hour in seconds
_BLM_SERVICE_URL = (
    "https://gis.blm.gov/arcgis/rest/services/lands/"
    "BLM_Natl_SMA_LimitedScale/MapServer/1/query"
)
_BLM_TILE_URL = (
    "https://gis.blm.gov/arcgis/rest/services/lands/"
    "BLM_Natl_SMA_LimitedScale/MapServer/tile/{z}/{y}/{x}"
)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
    tags=["meta"],
)
async def health_check(db: AsyncSession = Depends(get_db)) -> HealthResponse:
    """
    Return application liveness and basic database connectivity status.

    The ``database`` flag is ``True`` only if a simple ``SELECT 1`` succeeds.
    """
    db_ok = False
    try:
        await db.execute(text("SELECT 1"))
        db_ok = True
    except Exception as exc:
        logger.warning("Database health check failed: %s", exc)

    return HealthResponse(
        status="ok" if db_ok else "degraded",
        database=db_ok,
    )


# ---------------------------------------------------------------------------
# Locations (point features)
# ---------------------------------------------------------------------------

@router.get(
    "/locations",
    response_model=GeoJSONFeatureCollection,
    summary="All historical locations as GeoJSON",
    tags=["locations"],
)
async def get_locations(
    location_type: Optional[str] = Query(None, alias="type", description="Filter by location type"),
    min_confidence: float = Query(0.0, ge=0.0, le=1.0, description="Minimum confidence threshold"),
    limit: int = Query(2000, ge=1, le=10000, description="Maximum number of records to return"),
    db: AsyncSession = Depends(get_db),
) -> GeoJSONFeatureCollection:
    """
    Return all point-based historical locations as a GeoJSON FeatureCollection.

    Optional query parameters allow filtering by ``type`` and minimum
    ``confidence`` score.
    """
    stmt = select(Location).where(Location.confidence >= min_confidence)

    if location_type:
        stmt = stmt.where(Location.type == location_type)

    stmt = stmt.limit(limit).order_by(Location.confidence.desc())

    result = await db.execute(stmt)
    locations = result.scalars().all()

    features = []
    for loc in locations:
        if loc.latitude is None or loc.longitude is None:
            continue
        features.append(
            {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [loc.longitude, loc.latitude],
                },
                "properties": {
                    "id": str(loc.id),
                    "name": loc.name,
                    "type": loc.type.value if hasattr(loc.type, "value") else loc.type,
                    "year": loc.year,
                    "description": loc.description,
                    "source": loc.source,
                    "confidence": loc.confidence,
                },
            }
        )

    return GeoJSONFeatureCollection(type="FeatureCollection", features=features)


@router.post(
    "/locations",
    response_model=LocationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a historical location",
    tags=["locations"],
)
async def create_location(
    payload: LocationCreate,
    db: AsyncSession = Depends(get_db),
) -> LocationResponse:
    """
    Insert a new historical location record into the database.

    The PostGIS ``geom`` column is populated automatically from the
    supplied ``latitude`` and ``longitude`` values.
    """
    geom_expr = ST_SetSRID(
        ST_MakePoint(payload.longitude, payload.latitude), 4326
    )

    loc = Location(
        id=uuid4(),
        name=payload.name,
        type=payload.type.value,
        latitude=payload.latitude,
        longitude=payload.longitude,
        year=payload.year,
        description=payload.description,
        source=payload.source,
        confidence=payload.confidence,
        geom=geom_expr,
    )
    db.add(loc)
    await db.flush()
    await db.refresh(loc)

    return LocationResponse(
        id=loc.id,
        name=loc.name,
        type=loc.type,
        latitude=loc.latitude,
        longitude=loc.longitude,
        year=loc.year,
        description=loc.description,
        source=loc.source,
        confidence=loc.confidence,
    )


# ---------------------------------------------------------------------------
# Linear features (trails / railroads)
# ---------------------------------------------------------------------------

@router.get(
    "/features",
    response_model=GeoJSONFeatureCollection,
    summary="All linear features (trails, railroads) as GeoJSON",
    tags=["features"],
)
async def get_features(
    feature_type: Optional[str] = Query(None, alias="type", description="Filter by feature type"),
    limit: int = Query(500, ge=1, le=5000),
    db: AsyncSession = Depends(get_db),
) -> GeoJSONFeatureCollection:
    """
    Return all linear geographic features (trails, railroads) as a GeoJSON
    FeatureCollection with LineString geometries.

    When the ``geom`` column is populated the coordinates are read from
    PostGIS; otherwise the feature is omitted from the response.
    """
    stmt = select(LinearFeature)
    if feature_type:
        stmt = stmt.where(LinearFeature.type == feature_type)
    stmt = stmt.limit(limit)

    result = await db.execute(stmt)
    features_db = result.scalars().all()

    features = []
    for feat in features_db:
        # Only include features that have geometry stored
        if feat.geom is None:
            continue

        # Attempt to retrieve the geometry as GeoJSON from PostGIS
        geom_result = await db.execute(
            select(
                func.ST_AsGeoJSON(LinearFeature.geom).label("geojson")
            ).where(LinearFeature.id == feat.id)
        )
        geom_row = geom_result.fetchone()
        if geom_row is None or geom_row.geojson is None:
            continue

        geom_dict = json.loads(geom_row.geojson)

        features.append(
            {
                "type": "Feature",
                "geometry": geom_dict,
                "properties": {
                    "id": str(feat.id),
                    "name": feat.name,
                    "type": feat.type.value if hasattr(feat.type, "value") else feat.type,
                    "source": feat.source,
                },
            }
        )

    return GeoJSONFeatureCollection(type="FeatureCollection", features=features)


# ---------------------------------------------------------------------------
# Heatmap
# ---------------------------------------------------------------------------

@router.get(
    "/heatmap",
    response_model=List[HeatmapPoint],
    summary="Weighted heatmap data",
    tags=["analysis"],
)
async def get_heatmap(
    min_confidence: float = Query(0.0, ge=0.0, le=1.0),
    db: AsyncSession = Depends(get_db),
) -> List[HeatmapPoint]:
    """
    Return a list of ``{lat, lon, weight}`` objects for use as heatmap
    input data.

    Weights are normalised to [0, 1] and reflect both the historical
    significance of each location type and the age of the site.
    """
    stmt = select(
        Location.latitude,
        Location.longitude,
        Location.type,
        Location.year,
        Location.confidence,
    ).where(
        Location.latitude.isnot(None),
        Location.longitude.isnot(None),
        Location.confidence >= min_confidence,
    )

    result = await db.execute(stmt)
    rows = result.fetchall()

    raw: List[Dict[str, Any]] = [
        {
            "latitude": row.latitude,
            "longitude": row.longitude,
            "type": row.type.value if hasattr(row.type, "value") else row.type,
            "year": row.year,
            "confidence": row.confidence,
        }
        for row in rows
    ]

    points = compute_heatmap_data(raw)
    return [HeatmapPoint(lat=p["lat"], lon=p["lon"], weight=p["weight"]) for p in points]


# ---------------------------------------------------------------------------
# Score
# ---------------------------------------------------------------------------

@router.get(
    "/score",
    response_model=ScoreResponse,
    summary="Compute metal-detecting interest score for a coordinate",
    tags=["analysis"],
)
async def get_score(
    lat: float = Query(..., ge=-90.0, le=90.0, description="Latitude of the query point"),
    lon: float = Query(..., ge=-180.0, le=180.0, description="Longitude of the query point"),
    radius_km: float = Query(
        settings.SCORE_SEARCH_RADIUS_KM,
        ge=0.1,
        le=100.0,
        description="Search radius in kilometres",
    ),
    db: AsyncSession = Depends(get_db),
) -> ScoreResponse:
    """
    Compute a 0–100 metal-detecting interest score for the supplied coordinate.

    The score is based on:
    - Proximity and type of nearby historical locations (within ``radius_km``).
    - Presence of nearby linear features (trails, railroads, waterways).
    - Age of nearby sites.
    - Overlap multiplier when multiple significant sites cluster together.
    """
    # Convert radius from km to metres for geography-based distance query
    radius_m = radius_km * 1000.0

    point_expr = ST_SetSRID(ST_MakePoint(lon, lat), 4326)

    # Query nearby point locations
    loc_stmt = select(
        Location.type,
        Location.latitude,
        Location.longitude,
        Location.year,
        Location.name,
        Location.confidence,
    ).where(
        Location.latitude.isnot(None),
        Location.longitude.isnot(None),
        Location.geom.isnot(None),
        ST_DWithin(
            cast(Location.geom, Geography),
            cast(point_expr, Geography),
            radius_m,
        ),
    )
    loc_result = await db.execute(loc_stmt)
    nearby_locs: List[Dict[str, Any]] = [
        {
            "type": row.type.value if hasattr(row.type, "value") else row.type,
            "latitude": row.latitude,
            "longitude": row.longitude,
            "year": row.year,
            "name": row.name,
            "confidence": row.confidence,
        }
        for row in loc_result.fetchall()
    ]

    # Query nearby linear features
    feat_stmt = select(
        LinearFeature.type,
        LinearFeature.name,
    ).where(
        LinearFeature.geom.isnot(None),
        ST_DWithin(
            cast(LinearFeature.geom, Geography),
            cast(point_expr, Geography),
            radius_m,
        ),
    )
    feat_result = await db.execute(feat_stmt)
    nearby_feats: List[Dict[str, Any]] = [
        {
            "type": row.type.value if hasattr(row.type, "value") else row.type,
            "name": row.name,
        }
        for row in feat_result.fetchall()
    ]

    result = score_location(lat, lon, nearby_locs, nearby_feats)

    return ScoreResponse(
        lat=lat,
        lon=lon,
        score=result["score"],
        breakdown=result["breakdown"],
        nearby_count=result["nearby_count"],
    )


# ---------------------------------------------------------------------------
# State bounding boxes (min_lat, max_lat, min_lon, max_lon)
# ---------------------------------------------------------------------------

_STATE_BBOX: Dict[str, tuple] = {
    "CO": (37.0, 41.0, -109.05, -102.05),
    "CA": (32.5, 42.0, -124.5, -114.1),
    "AZ": (31.3, 37.0, -114.8, -109.05),
    "NM": (31.3, 37.0, -109.05, -103.0),
    "TX": (25.8, 36.5, -106.65, -93.5),
    "PA": (39.7, 42.3, -80.5, -74.7),
    "VA": (36.5, 39.5, -83.7, -75.2),
    "WV": (37.2, 40.6, -82.7, -77.7),
    "TN": (34.98, 36.68, -90.3, -81.65),
    "KY": (36.5, 39.15, -89.6, -81.95),
    "GA": (30.36, 35.0, -85.6, -80.85),
    "WY": (41.0, 45.0, -111.05, -104.05),
    "MT": (44.35, 49.0, -116.05, -104.05),
    "ID": (42.0, 49.0, -117.25, -111.05),
    "OR": (42.0, 46.25, -124.55, -116.45),
    "NV": (35.0, 42.0, -120.0, -114.05),
    "SD": (42.5, 45.95, -104.05, -96.45),
    "OK": (33.6, 37.0, -103.0, -94.43),
    "AR": (33.0, 36.5, -94.6, -89.65),
    "MO": (35.99, 40.6, -95.77, -89.1),
    "KS": (37.0, 40.0, -102.05, -94.6),
    "NE": (40.0, 43.0, -104.05, -95.31),
    "UT": (37.0, 42.0, -114.05, -109.05),
}


# ---------------------------------------------------------------------------
# Hotspot cluster detection
# ---------------------------------------------------------------------------

@router.get(
    "/hotspots",
    response_model=List[HotspotCluster],
    summary="Discover top spatial hotspot clusters of historical locations",
    tags=["analysis"],
)
async def get_hotspots(
    top_n: int = Query(20, ge=1, le=100, description="Number of top clusters to return"),
    min_cluster_size: int = Query(3, ge=1, description="Minimum locations per cluster"),
    eps_km: float = Query(5.0, ge=0.1, le=500.0, description="Clustering radius in kilometres"),
    state: Optional[str] = Query(None, description="US state abbreviation for bounding-box filter (e.g. CO)"),
    db: AsyncSession = Depends(get_db),
) -> List[HotspotCluster]:
    """
    Use PostGIS ``ST_ClusterDBSCAN`` to find spatial clusters of historical
    locations and return the top N clusters ranked by aggregate score.

    The aggregate score for each cluster is the sum of ``(type_weight × confidence)``
    across all member locations.  State filtering restricts the input set to a
    predefined bounding box before clustering.
    """
    from app.scoring.engine import WEIGHTS

    # Approximate eps in degrees (acceptable for clustering purposes)
    eps_deg = eps_km / 111.0

    # Build bounding-box filter clause
    bbox_clause = ""
    bbox_params: Dict[str, float] = {}
    if state:
        state_upper = state.upper()
        if state_upper not in _STATE_BBOX:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Unknown state abbreviation: '{state}'. Supported: {sorted(_STATE_BBOX)}",
            )
        min_lat, max_lat, min_lon, max_lon = _STATE_BBOX[state_upper]
        bbox_clause = (
            "AND latitude BETWEEN :min_lat AND :max_lat "
            "AND longitude BETWEEN :min_lon AND :max_lon"
        )
        bbox_params = {
            "min_lat": min_lat,
            "max_lat": max_lat,
            "min_lon": min_lon,
            "max_lon": max_lon,
        }

    cluster_sql = text(
        f"""
        SELECT
            name,
            type,
            latitude,
            longitude,
            confidence,
            ST_ClusterDBSCAN(geom, eps := :eps_deg, minpoints := :min_size) OVER () AS cluster_id
        FROM locations
        WHERE geom IS NOT NULL
          AND latitude IS NOT NULL
          AND longitude IS NOT NULL
        {bbox_clause}
        """
    )

    result = await db.execute(
        cluster_sql,
        {"eps_deg": eps_deg, "min_size": min_cluster_size, **bbox_params},
    )
    rows = result.fetchall()

    # Group rows by cluster_id (None = noise, skip)
    clusters: Dict[int, List[Any]] = {}
    for row in rows:
        cid = row.cluster_id
        if cid is None:
            continue
        clusters.setdefault(cid, []).append(row)

    # Compute per-cluster stats
    output: List[HotspotCluster] = []
    for cid, members in clusters.items():
        if len(members) < min_cluster_size:
            continue

        lats = [m.latitude for m in members]
        lons = [m.longitude for m in members]
        centroid_lat = sum(lats) / len(lats)
        centroid_lon = sum(lons) / len(lons)

        types_present = list({
            m.type.value if hasattr(m.type, "value") else m.type
            for m in members
        })

        aggregate_score = sum(
            WEIGHTS.get(
                m.type.value if hasattr(m.type, "value") else m.type,
                WEIGHTS.get("event", 40.0),
            ) * float(m.confidence if m.confidence is not None else 0.5)
            for m in members
        )

        # Top 5 by (weight × confidence)
        sorted_members = sorted(
            members,
            key=lambda m: WEIGHTS.get(
                m.type.value if hasattr(m.type, "value") else m.type,
                WEIGHTS.get("event", 40.0),
            ) * float(m.confidence if m.confidence is not None else 0.5),
            reverse=True,
        )
        top_locations = [m.name for m in sorted_members[:5]]

        output.append(
            HotspotCluster(
                cluster_id=cid,
                centroid_lat=centroid_lat,
                centroid_lon=centroid_lon,
                location_count=len(members),
                aggregate_score=round(aggregate_score, 2),
                types_present=types_present,
                top_locations=top_locations,
            )
        )

    # Sort by aggregate score descending, return top N
    output.sort(key=lambda c: c.aggregate_score, reverse=True)
    return output[:top_n]


# ---------------------------------------------------------------------------
# Scrape trigger (admin)
# ---------------------------------------------------------------------------

@router.post(
    "/scrape",
    summary="Trigger Wikipedia scrape and ingest results",
    tags=["admin"],
    status_code=status.HTTP_202_ACCEPTED,
)
async def trigger_scrape(
    geocode_missing: bool = Query(True, description="Geocode records without explicit coordinates"),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    Trigger an async scrape of all configured Wikipedia pages and insert
    the results into the database.

    Duplicate records (same name + type) are silently skipped using an
    ON CONFLICT DO NOTHING strategy emulated via a pre-check query.

    This endpoint is intended for administrative / seeding use only.
    In production, wrap it behind authentication middleware.
    """
    from app.scrapers.wikipedia import scrape_all

    records = await scrape_all(geocode_missing=geocode_missing)
    inserted = 0
    skipped = 0

    for rec in records:
        if rec.get("latitude") is None or rec.get("longitude") is None:
            skipped += 1
            continue

        # Lightweight duplicate check
        exists = await db.execute(
            select(Location.id).where(
                Location.name == rec["name"],
                Location.type == rec["type"],
            )
        )
        if exists.first() is not None:
            skipped += 1
            continue

        geom = ST_SetSRID(ST_MakePoint(rec["longitude"], rec["latitude"]), 4326)
        loc = Location(
            id=uuid4(),
            name=rec["name"],
            type=rec["type"],
            latitude=rec["latitude"],
            longitude=rec["longitude"],
            year=rec.get("year"),
            description=rec.get("description"),
            source=rec.get("source"),
            confidence=rec.get("confidence", 0.5),
            geom=geom,
        )
        db.add(loc)
        inserted += 1

    await db.flush()
    logger.info("Scrape complete: %d inserted, %d skipped", inserted, skipped)

    return {
        "status": "accepted",
        "inserted": inserted,
        "skipped": skipped,
        "total_scraped": len(records),
    }


# ---------------------------------------------------------------------------
# BLM public lands
# ---------------------------------------------------------------------------

@router.get(
    "/blm-lands/tile-url",
    summary="BLM tile service URL for direct map rendering",
    tags=["analysis"],
)
async def get_blm_tile_url() -> Dict[str, str]:
    """
    Return the BLM tile service URL and attribution metadata.

    The URL uses the standard ``{z}/{y}/{x}`` format (note: y before x as
    required by the BLM ArcGIS tile service).
    """
    return {
        "url": _BLM_TILE_URL,
        "attribution": "Bureau of Land Management",
        "description": (
            "BLM Surface Management Agency lands — "
            "public land open to metal detecting with permit"
        ),
    }


@router.get(
    "/blm-lands",
    response_model=GeoJSONFeatureCollection,
    summary="BLM public lands within radius (legally detectable areas)",
    tags=["analysis"],
)
async def get_blm_lands(
    lat: float = Query(..., ge=-90.0, le=90.0),
    lon: float = Query(..., ge=-180.0, le=180.0),
    radius_km: float = Query(50.0, ge=1.0, le=500.0),
    response: Response = None,  # type: ignore[assignment]
) -> GeoJSONFeatureCollection:
    """
    Return BLM public land boundaries within ``radius_km`` of the supplied
    coordinate as a GeoJSON FeatureCollection.

    Results are cached in memory for one hour.  When the upstream BLM
    ArcGIS service is unavailable an empty FeatureCollection is returned
    with a ``X-BLM-Warning`` response header.
    """
    import httpx

    cache_key = f"{lat:.4f}:{lon:.4f}:{radius_km:.1f}"
    now = time.monotonic()

    # Return cached result if fresh
    if cache_key in _BLM_CACHE:
        ts, cached_data = _BLM_CACHE[cache_key]
        if now - ts < _BLM_CACHE_TTL:
            return cached_data

    # Build a simple bounding-box envelope from radius (approximate)
    deg_per_km = 1.0 / 111.0
    delta = radius_km * deg_per_km
    envelope = (
        f"{lon - delta},{lat - delta},{lon + delta},{lat + delta}"
    )

    params = {
        "geometry": envelope,
        "geometryType": "esriGeometryEnvelope",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "ADMU_NAME,ADMIN_ST,NLCS_DESC",
        "f": "geojson",
        "resultRecordCount": 500,
    }

    empty_collection = GeoJSONFeatureCollection(
        type="FeatureCollection", features=[]
    )

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(_BLM_SERVICE_URL, params=params)
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:
        logger.warning("BLM API unavailable: %s", exc)
        if response is not None:
            response.headers["X-BLM-Warning"] = "BLM data unavailable"
        _BLM_CACHE[cache_key] = (now, empty_collection)
        return empty_collection

    features = []
    for feat in data.get("features", []):
        props = feat.get("properties") or {}
        features.append(
            {
                "type": "Feature",
                "geometry": feat.get("geometry"),
                "properties": {
                    "name": props.get("ADMU_NAME", "BLM Land"),
                    "state": props.get("ADMIN_ST", ""),
                    "admin_unit": props.get("NLCS_DESC", ""),
                },
            }
        )

    result = GeoJSONFeatureCollection(type="FeatureCollection", features=features)
    _BLM_CACHE[cache_key] = (now, result)
    return result
