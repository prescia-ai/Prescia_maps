"""
Aurik – FastAPI route definitions.

All routes are mounted under the ``/api/v1`` prefix defined in
``main.py``.  Each endpoint relies on an injected async SQLAlchemy
session (``db``) and, where appropriate, calls the scoring engine.
"""

import asyncio
import logging
import os
from collections import defaultdict
from typing import Any, Dict, List, Optional
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from geoalchemy2.shape import from_shape
from shapely.geometry import LineString as ShapelyLineString
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import Response

from app.models.database import (
    LandAccessCache,
    LandAccessOverride,
    LinearFeature,
    Location,
    MapLayer,
    Badge,
    UserBadge,
    get_db,
)
from app.models.schemas import (
    BadgeProgressResponse,
    BadgeResponse,
    FeatureResponse,
    GeoJSONFeatureCollection,
    HealthResponse,
    HeatmapPoint,
    HotspotCluster,
    ImportFeaturesRequest,
    ImportLocationItem,
    ImportSummaryResponse,
    LandAccessOverrideCreate,
    LandAccessOverrideResponse,
    LandAccessResponse,
    LinearFeatureProperties,
    LineStringGeometry,
    LocationCreate,
    LocationProperties,
    LocationResponse,
    MapLayerCreate,
    MapLayerResponse,
    NewlyEarnedBadgesResponse,
    PointGeometry,
    ScoreResponse,
)
from app.scoring.engine import WEIGHTS, _age_bonus, compute_heatmap_data, score_location
from app.services.land_access import lookup_land_access
from app.services.badge_service import check_all_badges, get_badge_progress
from app.auth.deps import get_current_user as _get_current_user

logger = logging.getLogger(__name__)

# PAD-US 4.1 Combined FeatureServer (USGS GAP Analysis Project on ArcGIS Online).
# Override via the PADUS_FEATURE_SERVICE_URL environment variable.
_PADUS_DEFAULT_URL = (
    "https://services.arcgis.com/VTyQ9soqVukalItT/arcgis/rest/services"
    "/PADUS4_1Combined/FeatureServer/0/query"
)
PADUS_FEATURE_SERVICE_URL: str = os.environ.get(
    "PADUS_FEATURE_SERVICE_URL", _PADUS_DEFAULT_URL
)

router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _esri_to_geojson(esri_data: Dict[str, Any]) -> Dict[str, Any]:
    """Convert an esriJSON FeatureSet to a GeoJSON FeatureCollection.

    Handles Polygon and MultiPolygon ring structures.  Used as a fallback
    when the upstream service does not support ``f=geojson``.
    """

    def _rings_to_geom(rings: list) -> Dict[str, Any]:
        if len(rings) == 1:
            return {"type": "Polygon", "coordinates": rings}
        return {"type": "MultiPolygon", "coordinates": [[r] for r in rings]}

    features = []
    for feat in esri_data.get("features", []):
        geom = feat.get("geometry")
        attrs = feat.get("attributes", {})
        if geom and "rings" in geom:
            geo = _rings_to_geom(geom["rings"])
        elif geom and "x" in geom and "y" in geom:
            geo = {"type": "Point", "coordinates": [geom["x"], geom["y"]]}
        else:
            geo = None
        features.append({"type": "Feature", "geometry": geo, "properties": attrs})
    return {"type": "FeatureCollection", "features": features}


def _type_str(value: Any) -> str:
    """Return the string representation of an ORM enum value."""
    return value.value if hasattr(value, "value") else str(value)

# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
    tags=["health"],
)
async def health_check(db: AsyncSession = Depends(get_db)) -> HealthResponse:
    """Return application health status and database connectivity."""
    db_ok = False
    try:
        await db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        pass
    return HealthResponse(
        status="ok" if db_ok else "degraded",
        database=db_ok,
    )


# ---------------------------------------------------------------------------
# Locations
# ---------------------------------------------------------------------------


@router.get(
    "/locations",
    response_model=GeoJSONFeatureCollection,
    summary="List all historical locations as GeoJSON",
    tags=["locations"],
)
async def get_locations(
    type_filter: Optional[str] = Query(None, alias="type"),
    source: Optional[str] = Query(None),
    limit: int = Query(5000, ge=1, le=100000),
    per_type_limit: Optional[int] = Query(None, ge=1, le=10000),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> GeoJSONFeatureCollection:
    """
    Return historical locations as a GeoJSON FeatureCollection.

    Supports optional filtering by ``type`` and ``source``.

    When ``per_type_limit`` is set (and no ``type`` filter is active), returns
    up to that many records **per location type** so that all categories are
    represented on the map even when one type (e.g. mines) vastly outnumbers
    the others.
    """
    if per_type_limit is not None and not type_filter:
        # Balanced query: up to per_type_limit records per type, ordered by id
        # so results are consistent across calls.
        # Split into two branches to avoid passing None as a bind parameter,
        # which causes asyncpg AmbiguousParameterError.
        if source is not None:
            balanced_sql = text(
                """
                SELECT id, name, type, latitude, longitude, year, description,
                       source, confidence
                FROM (
                    SELECT id, name, type, latitude, longitude, year, description,
                           source, confidence,
                           ROW_NUMBER() OVER (PARTITION BY type ORDER BY id) AS rn
                    FROM locations
                    WHERE source = :source_filter
                ) ranked
                WHERE rn <= :per_type_limit
                ORDER BY type, id
                """
            ).bindparams(
                per_type_limit=per_type_limit,
                source_filter=source,
            )
        else:
            # Community-approved pins (source LIKE 'community:%') are always
            # included in full so a newly approved pin is never cut off by the
            # per-type cap.  Non-community pins are still balanced.
            balanced_sql = text(
                """
                SELECT id, name, type, latitude, longitude, year, description,
                       source, confidence
                FROM (
                    SELECT id, name, type, latitude, longitude, year, description,
                           source, confidence,
                           ROW_NUMBER() OVER (PARTITION BY type ORDER BY id) AS rn
                    FROM locations
                    WHERE (source NOT LIKE 'community:%' OR source IS NULL)
                    -- NULL source must be kept: NULL NOT LIKE '...' evaluates to NULL (falsy)
                ) ranked
                WHERE rn <= :per_type_limit
                UNION ALL
                SELECT id, name, type, latitude, longitude, year, description,
                       source, confidence
                FROM locations
                WHERE source LIKE 'community:%'
                ORDER BY type, id
                """
            ).bindparams(
                per_type_limit=per_type_limit,
            )
        result = await db.execute(balanced_sql)
        rows = result.mappings().all()

        features: List[FeatureResponse] = []
        for row in rows:
            features.append(
                FeatureResponse(
                    geometry=PointGeometry(
                        coordinates=[row["longitude"], row["latitude"]]
                    ),
                    properties=LocationProperties(
                        id=row["id"],
                        name=row["name"],
                        type=row["type"],
                        year=row["year"],
                        description=row["description"],
                        source=row["source"],
                        confidence=row["confidence"],
                    ),
                )
            )
        return GeoJSONFeatureCollection(features=features)

    stmt = select(Location)
    if type_filter:
        stmt = stmt.where(Location.type == type_filter)
    if source:
        stmt = stmt.where(Location.source == source)
    stmt = stmt.offset(offset).limit(limit)

    result = await db.execute(stmt)
    locations = result.scalars().all()

    features: List[FeatureResponse] = []
    for loc in locations:
        features.append(
            FeatureResponse(
                geometry=PointGeometry(coordinates=[loc.longitude, loc.latitude]),
                properties=LocationProperties(
                    id=loc.id,
                    name=loc.name,
                    type=loc.type,
                    year=loc.year,
                    description=loc.description,
                    source=loc.source,
                    confidence=loc.confidence,
                ),
            )
        )

    return GeoJSONFeatureCollection(features=features)


@router.post(
    "/locations",
    response_model=LocationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new historical location",
    tags=["locations"],
)
async def create_location(
    payload: LocationCreate,
    db: AsyncSession = Depends(get_db),
) -> LocationResponse:
    """Insert a new historical location into the database."""
    loc = Location(
        name=payload.name,
        type=payload.type,
        latitude=payload.latitude,
        longitude=payload.longitude,
        year=payload.year,
        description=payload.description,
        source=payload.source,
        confidence=payload.confidence,
    )
    db.add(loc)
    await db.flush()
    await db.refresh(loc)
    return LocationResponse.model_validate(loc)


@router.get(
    "/locations/{location_id}",
    response_model=LocationResponse,
    summary="Get a single historical location",
    tags=["locations"],
)
async def get_location(
    location_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> LocationResponse:
    """Return a single historical location by its UUID."""
    result = await db.execute(select(Location).where(Location.id == location_id))
    loc = result.scalar_one_or_none()
    if loc is None:
        raise HTTPException(status_code=404, detail="Location not found")
    return LocationResponse.model_validate(loc)


@router.delete(
    "/locations/{location_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Delete a historical location",
    tags=["locations"],
)
async def delete_location(
    location_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Delete a historical location by its UUID."""
    result = await db.execute(select(Location).where(Location.id == location_id))
    loc = result.scalar_one_or_none()
    if loc is None:
        raise HTTPException(status_code=404, detail="Location not found")
    await db.delete(loc)


# ---------------------------------------------------------------------------
# Linear features
# ---------------------------------------------------------------------------


@router.get(
    "/features",
    response_model=GeoJSONFeatureCollection,
    summary="List all linear geographic features as GeoJSON",
    tags=["features"],
)
async def get_features(
    type_filter: Optional[str] = Query(None, alias="type"),
    limit: int = Query(500, ge=1, le=5000),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> GeoJSONFeatureCollection:
    """Return all linear features (trails, railroads, rivers) as GeoJSON."""
    stmt = select(LinearFeature)
    if type_filter:
        stmt = stmt.where(LinearFeature.type == type_filter)
    stmt = stmt.offset(offset).limit(limit)

    result = await db.execute(stmt)
    features_db = result.scalars().all()

    features: List[FeatureResponse] = []
    for feat in features_db:
        if feat.geom is None:
            continue
        # Extract coordinates from WKB geometry via PostGIS using the row id
        coords_result = await db.execute(
            text(
                "SELECT ST_AsGeoJSON(geom)::json->'coordinates' "
                "FROM linear_features WHERE id = :feat_id"
            ).bindparams(feat_id=feat.id)
        )
        coords_row = coords_result.fetchone()
        if coords_row is None or coords_row[0] is None:
            continue
        coordinates = coords_row[0]

        features.append(
            FeatureResponse(
                geometry=LineStringGeometry(coordinates=coordinates),
                properties=LinearFeatureProperties(
                    id=feat.id,
                    name=feat.name,
                    type=feat.type,
                    source=feat.source,
                ),
            )
        )

    return GeoJSONFeatureCollection(features=features)


# ---------------------------------------------------------------------------
# Heatmap
# ---------------------------------------------------------------------------


@router.get(
    "/heatmap",
    response_model=List[HeatmapPoint],
    summary="Heatmap weight data for all locations",
    tags=["scoring"],
)
async def get_heatmap(
    zoom: int = Query(10, ge=1, le=20, description="Current map zoom level"),
    db: AsyncSession = Depends(get_db),
) -> List[HeatmapPoint]:
    """
    Return weighted heatmap points for all historical locations.

    The zoom level controls how points are processed:
    - Low zoom (≤7): grid-clustered regional hotspots (fewer, broader points)
    - Mid zoom (8–12): spatially interpolated grid so the area between
      two historical sites glows warm, not cold
    - High zoom (≥13): raw location points with tight precision

    Each point's weight is normalised to [0, 1].
    """
    result = await db.execute(
        select(
            Location.id,
            Location.latitude,
            Location.longitude,
            Location.type,
            Location.year,
            Location.name,
            Location.description,
            Location.confidence,
        )
    )
    rows = result.all()

    all_locs = [
        {
            "id": str(r.id),
            "latitude": r.latitude,
            "longitude": r.longitude,
            "type": _type_str(r.type),
            "year": r.year,
            "name": r.name or "",
            "description": r.description or "",
            "confidence": r.confidence,
        }
        for r in rows
    ]

    raw_points = compute_heatmap_data(all_locs, zoom=zoom)
    return [HeatmapPoint(**p) for p in raw_points]


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------


@router.get(
    "/score",
    response_model=ScoreResponse,
    summary="Score a coordinate for metal-detecting interest",
    tags=["scoring"],
)
async def get_score(
    lat: float = Query(..., ge=-90.0, le=90.0, description="Latitude"),
    lon: float = Query(..., ge=-180.0, le=180.0, description="Longitude"),
    radius_km: float = Query(10.0, ge=0.1, le=100.0, description="Search radius in km"),
    db: AsyncSession = Depends(get_db),
) -> ScoreResponse:
    """
    Compute a 0–100 metal-detecting interest score for the given coordinate.

    Searches for all historical locations and linear features within
    ``radius_km`` and calls the scoring engine.
    """
    # Nearby locations via PostGIS
    nearby_locs_result = await db.execute(
        text(
            """
            SELECT id, name, type, latitude, longitude, year, description, confidence
            FROM locations
            WHERE ST_DWithin(
                geom::geography,
                ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography,
                :radius_m
            )
            """
        ).bindparams(lat=lat, lon=lon, radius_m=radius_km * 1000)
    )
    nearby_locs = [
        {
            "id": str(r[0]),
            "name": r[1],
            "type": _type_str(r[2]),
            "latitude": r[3],
            "longitude": r[4],
            "year": r[5],
            "description": r[6] or "",
            "confidence": r[7],
        }
        for r in nearby_locs_result.all()
    ]

    # Nearby linear features
    nearby_feats_result = await db.execute(
        text(
            """
            SELECT name, type
            FROM linear_features
            WHERE ST_DWithin(
                geom::geography,
                ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography,
                :radius_m
            )
            """
        ).bindparams(lat=lat, lon=lon, radius_m=radius_km * 1000)
    )
    nearby_feats = [
        {
            "name": r[0],
            "type": _type_str(r[1]),
        }
        for r in nearby_feats_result.all()
    ]

    result = score_location(lat, lon, nearby_locs, nearby_feats)

    # Land access lookup — best-effort with a 4-second timeout so the score
    # endpoint doesn't hang if PAD-US is unavailable.
    accessible: Optional[str] = None
    try:
        land_info = await asyncio.wait_for(
            lookup_land_access(lat, lon, db),
            timeout=4.0,
        )
        accessible = land_info.get("status", "unknown")
    except asyncio.TimeoutError:
        logger.warning("Land access lookup timed out for (%s, %s)", lat, lon)
        accessible = "unknown"
    except Exception:
        logger.exception("Land access lookup failed for (%s, %s)", lat, lon)
        accessible = "unknown"

    return ScoreResponse(
        lat=lat,
        lon=lon,
        score=result["score"],
        raw_score=result.get("raw_score"),
        breakdown=result["breakdown"],
        nearby_count=result["nearby_count"],
        accessible=accessible,
    )


# ---------------------------------------------------------------------------
# Hotspot clusters
# ---------------------------------------------------------------------------


@router.get(
    "/hotspots",
    response_model=List[HotspotCluster],
    summary="Return top spatial clusters of historical activity",
    tags=["scoring"],
)
async def get_hotspots(
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> List[HotspotCluster]:
    """
    Return the top ``limit`` spatial clusters ranked by aggregate score.

    Uses a simple grid-based clustering (0.5° cells).
    """
    result = await db.execute(
        select(
            Location.latitude,
            Location.longitude,
            Location.type,
            Location.name,
            Location.year,
            Location.confidence,
        )
    )
    rows = result.all()

    cells: Dict = defaultdict(list)
    for r in rows:
        cell_lat = round(r.latitude / 0.5) * 0.5
        cell_lon = round(r.longitude / 0.5) * 0.5
        cells[(cell_lat, cell_lon)].append(r)

    clusters: List[HotspotCluster] = []
    for cluster_id, ((cell_lat, cell_lon), locs) in enumerate(
        sorted(cells.items(), key=lambda x: len(x[1]), reverse=True)[:limit]
    ):
        agg = sum(
            WEIGHTS.get(_type_str(l.type), WEIGHTS["event"]) * float(l.confidence)
            + _age_bonus(l.year)
            for l in locs
        )
        types_present = list({_type_str(l.type) for l in locs})
        top_names = [l.name for l in locs[:5] if l.name]
        clusters.append(
            HotspotCluster(
                cluster_id=cluster_id,
                centroid_lat=cell_lat,
                centroid_lon=cell_lon,
                location_count=len(locs),
                aggregate_score=round(min(agg, 100.0), 2),
                types_present=types_present,
                top_locations=top_names,
            )
        )

    return clusters


# ---------------------------------------------------------------------------
# Map layers
# ---------------------------------------------------------------------------


@router.get(
    "/layers",
    response_model=List[MapLayerResponse],
    summary="List all registered map layers",
    tags=["layers"],
)
async def get_layers(
    db: AsyncSession = Depends(get_db),
) -> List[MapLayerResponse]:
    """Return all registered map tile/overlay layers."""
    result = await db.execute(select(MapLayer))
    layers = result.scalars().all()
    return [
        MapLayerResponse(
            id=layer.id,
            name=layer.name,
            type=layer.type,
            url=layer.url,
            metadata=layer.metadata_,
        )
        for layer in layers
    ]


@router.post(
    "/layers",
    response_model=MapLayerResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new map layer",
    tags=["layers"],
)
async def create_layer(
    payload: MapLayerCreate,
    db: AsyncSession = Depends(get_db),
) -> MapLayerResponse:
    """Register a new map tile/overlay layer."""
    layer = MapLayer(
        name=payload.name,
        type=payload.type,
        url=payload.url,
        metadata_=payload.metadata,
    )
    db.add(layer)
    await db.flush()
    await db.refresh(layer)
    return MapLayerResponse(
        id=layer.id,
        name=layer.name,
        type=layer.type,
        url=layer.url,
        metadata=layer.metadata_,
    )


# ---------------------------------------------------------------------------
# BLM lands
# ---------------------------------------------------------------------------


@router.get(
    "/blm-lands/tile-url",
    response_model=None,
    summary="Return the PAD-US land-access tile URL and attribution",
    tags=["land-access"],
)
async def get_blm_tile_url() -> Dict[str, str]:
    """
    Return the PAD-US (Protected Areas Database) tile URL.

    Replaces the previous BLM-only tile service with the comprehensive
    PAD-US 3.0 layer that covers all protected and public lands.
    """
    return {
        "url": "https://gis.blm.gov/arcgis/rest/services/lands/BLM_Natl_SMA_LimitedScale/MapServer/tile/{z}/{y}/{x}",
        "attribution": "BLM Surface Management Agency – Public Land Survey",
    }


@router.get(
    "/land-access/pad-us-proxy",
    response_model=None,
    summary="Proxy PAD-US protected areas data for map overlay",
    tags=["land-access"],
)
async def pad_us_proxy(
    bbox: str = Query(..., description="Bounding box: west,south,east,north"),
) -> Dict[str, Any]:
    """
    Proxy PAD-US (Protected Areas Database) requests to avoid CORS issues.

    Fetches protected area polygons from USGS ArcGIS REST API for the given
    bounding box and returns as GeoJSON.
    """
    # Validate bbox format: must be four comma-separated floats
    parts = bbox.split(",")
    if len(parts) != 4:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="bbox must be four comma-separated numbers: west,south,east,north",
        )
    try:
        west, south, east, north = (float(p) for p in parts)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="bbox values must be numeric",
        )
    if not (-180 <= west <= 180 and -180 <= east <= 180):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Longitude values must be between -180 and 180",
        )
    if not (-90 <= south <= 90 and -90 <= north <= 90):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Latitude values must be between -90 and 90",
        )

    url = PADUS_FEATURE_SERVICE_URL

    params = {
        "geometry": bbox,
        "geometryType": "esriGeometryEnvelope",
        "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "where": "1=1",
        "returnGeometry": "true",
        "outFields": "Mang_Name,GAP_Sts,Des_Tp,Unit_Nm",
        "resultRecordCount": "2000",
        "f": "geojson",
        "outSR": "4326",
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, params=params)
            if not response.is_success:
                content_type = response.headers.get("content-type", "")
                body_snippet = response.text[:500]
                logger.warning(
                    "PAD-US upstream returned %s (content-type: %s): %s",
                    response.status_code,
                    content_type,
                    body_snippet,
                )
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"PAD-US upstream returned {response.status_code}",
                )
            content_type = response.headers.get("content-type", "")
            if "json" not in content_type:
                logger.warning(
                    "PAD-US upstream returned unexpected content-type %s: %s",
                    content_type,
                    response.text[:500],
                )
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="PAD-US service returned an unexpected response format",
                )
            data = response.json()
            # If the service returned esriJSON (no "type" key), convert to GeoJSON.
            if "type" not in data:
                data = _esri_to_geojson(data)
            return data
    except HTTPException:
        raise
    except httpx.HTTPError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to fetch PAD-US data: {str(e)}",
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to parse PAD-US response: {str(e)}",
        )


@router.get(
    "/blm-lands",
    response_model=None,
    summary="BLM lands data for a bounding box",
    tags=["blm"],
)
async def get_blm_lands(
    response: Response,
    lat: float = Query(..., ge=-90.0, le=90.0),
    lon: float = Query(..., ge=-180.0, le=180.0),
    radius_km: float = Query(10.0, ge=0.1, le=500.0),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, object]:
    """
    Return BLM public-land presence near the given coordinate.

    Sets a ``X-BLM-Data-Source`` response header for client-side caching
    and cache-invalidation purposes.
    """
    response.headers["X-BLM-Data-Source"] = "BLM GeoCommunicator"

    # Query locations that lie within the search radius and have a BLM source
    nearby_result = await db.execute(
        text(
            """
            SELECT name, type, latitude, longitude, description, confidence
            FROM locations
            WHERE source ILIKE '%blm%'
              AND ST_DWithin(
                  geom::geography,
                  ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography,
                  :radius_m
              )
            ORDER BY confidence DESC
            LIMIT 100
            """
        ).bindparams(lat=lat, lon=lon, radius_m=radius_km * 1000)
    )
    rows = nearby_result.all()

    return {
        "lat": lat,
        "lon": lon,
        "radius_km": radius_km,
        "blm_sites": [
            {
                "name": r[0],
                "type": _type_str(r[1]),
                "latitude": r[2],
                "longitude": r[3],
                "description": r[4],
                "confidence": r[5],
            }
            for r in rows
        ],
        "count": len(rows),
    }


# ---------------------------------------------------------------------------
# Land Access
# ---------------------------------------------------------------------------


@router.get(
    "/land-access",
    response_model=LandAccessResponse,
    summary="Classify land-access status at a coordinate",
    tags=["land-access"],
)
async def get_land_access(
    lat: float = Query(..., ge=-90.0, le=90.0, description="Latitude"),
    lon: float = Query(..., ge=-180.0, le=180.0, description="Longitude"),
    db: AsyncSession = Depends(get_db),
) -> LandAccessResponse:
    """
    Query PAD-US for the parcel at (lat, lon), run the tier-based rule
    engine, and return a 4-colour classification.

    Resolution order: user override → cache → tier-1 rules.
    """
    result = await lookup_land_access(lat, lon, db)
    return LandAccessResponse(**result)


@router.put(
    "/land-access/{area_code}/override",
    response_model=LandAccessResponse,
    summary="Create or update a user override for a land area",
    tags=["land-access"],
)
async def put_land_access_override(
    area_code: str,
    payload: LandAccessOverrideCreate,
    db: AsyncSession = Depends(get_db),
) -> LandAccessResponse:
    """Save a user override and return the updated classification."""
    from datetime import datetime, timezone

    # Upsert the override
    existing = await db.execute(
        select(LandAccessOverride).where(LandAccessOverride.area_code == area_code)
    )
    row = existing.scalar_one_or_none()
    if row is not None:
        row.status = payload.status
        row.notes = payload.notes
        row.updated_at = datetime.now(timezone.utc)
    else:
        row = LandAccessOverride(
            area_code=area_code,
            status=payload.status,
            notes=payload.notes,
        )
        db.add(row)
    await db.flush()

    # Also look up cached info to return a full response
    cached = await db.execute(
        select(LandAccessCache).where(LandAccessCache.area_code == area_code)
    )
    cached_row = cached.scalar_one_or_none()

    return LandAccessResponse(
        area_code=area_code,
        unit_name=cached_row.unit_name if cached_row else None,
        managing_agency=cached_row.managing_agency if cached_row else None,
        designation=cached_row.designation if cached_row else None,
        state=cached_row.state if cached_row else None,
        gap_status=cached_row.gap_status if cached_row else None,
        status=payload.status,
        confidence=1.0,
        reason=f"User override: {payload.notes or 'No notes provided.'}",
        source="user_override",
        last_verified=row.updated_at.isoformat() if row.updated_at else datetime.now(timezone.utc).isoformat(),
    )


@router.delete(
    "/land-access/{area_code}/override",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Remove a user override",
    tags=["land-access"],
)
async def delete_land_access_override(
    area_code: str,
    db: AsyncSession = Depends(get_db),
):
    """Remove a user override, falling back to the rule engine."""
    result = await db.execute(
        select(LandAccessOverride).where(LandAccessOverride.area_code == area_code)
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Override not found")
    await db.delete(row)


@router.get(
    "/land-access/overrides",
    response_model=List[LandAccessOverrideResponse],
    summary="List all user overrides",
    tags=["land-access"],
)
async def list_land_access_overrides(
    db: AsyncSession = Depends(get_db),
) -> List[LandAccessOverrideResponse]:
    """Return all user-submitted land-access overrides."""
    result = await db.execute(select(LandAccessOverride))
    rows = result.scalars().all()
    return [
        LandAccessOverrideResponse(
            area_code=r.area_code,
            status=r.status,
            notes=r.notes,
            created_at=r.created_at.isoformat() if r.created_at else None,
            updated_at=r.updated_at.isoformat() if r.updated_at else None,
        )
        for r in rows
    ]


# ---------------------------------------------------------------------------
# Bulk import
# ---------------------------------------------------------------------------


@router.post(
    "/import/locations",
    response_model=ImportSummaryResponse,
    status_code=status.HTTP_200_OK,
    summary="Bulk-import point locations from a JSON array",
    tags=["import"],
)
async def import_locations(
    payload: List[ImportLocationItem],
    db: AsyncSession = Depends(get_db),
) -> ImportSummaryResponse:
    """
    Accept a JSON array of point locations and insert them into the database.

    Skips duplicate records (matched by exact name) and invalid records.
    Returns a summary of inserted, skipped, and errored rows.
    """
    inserted = 0
    skipped_duplicate = 0
    skipped_invalid = 0
    errors: List[str] = []

    # Fetch existing names once for efficient dedup
    existing_result = await db.execute(select(Location.name))
    existing_names: set = {row[0] for row in existing_result.all()}

    for idx, item in enumerate(payload):
        row_label = f"Row {idx + 1}"
        if item.name in existing_names:
            skipped_duplicate += 1
            continue

        try:
            loc = Location(
                name=item.name,
                type=item.type,
                latitude=item.latitude,
                longitude=item.longitude,
                year=item.year,
                description=item.description,
                source=item.source,
                confidence=item.confidence,
            )
            db.add(loc)
            existing_names.add(item.name)
            inserted += 1
        except Exception as exc:
            skipped_invalid += 1
            errors.append(f"{row_label}: {exc}")

    await db.flush()
    return ImportSummaryResponse(
        inserted=inserted,
        skipped_duplicate=skipped_duplicate,
        skipped_invalid=skipped_invalid,
        errors=errors,
    )


@router.post(
    "/import/features",
    response_model=ImportSummaryResponse,
    status_code=status.HTTP_200_OK,
    summary="Bulk-import linear features from a GeoJSON FeatureCollection",
    tags=["import"],
)
async def import_features(
    payload: ImportFeaturesRequest,
    db: AsyncSession = Depends(get_db),
) -> ImportSummaryResponse:
    """
    Accept a GeoJSON FeatureCollection of LineString features and insert them.

    Skips duplicates by name and validates that geometry has at least 2 points
    and that the feature type is a valid LinearFeatureType.
    Returns a summary of inserted, skipped, and errored rows.
    """
    from app.models.database import LinearFeatureType as DBLinearFeatureType
    from app.models.schemas import LinearFeatureType as SchemaLinearFeatureType

    inserted = 0
    skipped_duplicate = 0
    skipped_invalid = 0
    errors: List[str] = []

    # Fetch existing names once for efficient dedup
    existing_result = await db.execute(select(LinearFeature.name))
    existing_names: set = {row[0] for row in existing_result.all()}

    for idx, feature in enumerate(payload.features):
        row_label = f"Row {idx + 1}"
        props = feature.properties
        name = props.get("name")
        feat_type = props.get("type")

        if not name or not str(name).strip():
            skipped_invalid += 1
            errors.append(f"{row_label}: 'name' is required")
            continue

        name = str(name).strip()

        if name in existing_names:
            skipped_duplicate += 1
            continue

        # Validate type
        valid_types = {t.value for t in SchemaLinearFeatureType}
        if feat_type not in valid_types:
            skipped_invalid += 1
            errors.append(
                f"{row_label}: type '{feat_type}' is not a valid LinearFeatureType "
                f"(must be one of: {', '.join(sorted(valid_types))})"
            )
            continue

        # Validate coordinates
        coords = feature.geometry.coordinates
        if len(coords) < 2:
            skipped_invalid += 1
            errors.append(f"{row_label}: geometry must have at least 2 coordinate pairs")
            continue

        try:
            shapely_line = ShapelyLineString(coords)
            geom = from_shape(shapely_line, srid=4326)
            linear_feat = LinearFeature(
                name=name,
                type=feat_type,
                geom=geom,
                source=str(props.get("source", "")) or None,
            )
            db.add(linear_feat)
            existing_names.add(name)
            inserted += 1
        except Exception as exc:
            skipped_invalid += 1
            errors.append(f"{row_label}: {exc}")

    await db.flush()
    return ImportSummaryResponse(
        inserted=inserted,
        skipped_duplicate=skipped_duplicate,
        skipped_invalid=skipped_invalid,
        errors=errors,
    )


# ---------------------------------------------------------------------------
# Badges
# ---------------------------------------------------------------------------


@router.get(
    "/badges",
    response_model=List[BadgeResponse],
    summary="List all achievement badges",
    tags=["badges"],
)
async def list_badges(
    db: AsyncSession = Depends(get_db),
) -> List[BadgeResponse]:
    """Return all available achievement badges."""
    result = await db.execute(select(Badge).order_by(Badge.category, Badge.points))
    badges = result.scalars().all()
    return [BadgeResponse.from_orm_with_url(b) for b in badges]


@router.get(
    "/users/{username}/badges",
    response_model=List[BadgeResponse],
    summary="Get badges earned by a user",
    tags=["badges"],
)
async def get_user_badges(
    username: str,
    db: AsyncSession = Depends(get_db),
) -> List[BadgeResponse]:
    """Return all badges earned by the specified user."""
    from app.models.database import User

    user_result = await db.execute(
        select(User).where(User.username == username)
    )
    user = user_result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    result = await db.execute(
        select(Badge)
        .join(UserBadge, UserBadge.badge_id == Badge.id)
        .where(UserBadge.user_id == user.id)
        .order_by(UserBadge.earned_at)
    )
    badges = result.scalars().all()
    return [BadgeResponse.from_orm_with_url(b) for b in badges]


@router.get(
    "/users/me/badge-progress",
    response_model=List[BadgeProgressResponse],
    summary="Get current user's progress on all badges",
    tags=["badges"],
)
async def get_my_badge_progress(
    current_user=Depends(_get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[BadgeProgressResponse]:
    """Return earned status and progress toward unearned badges for the current user."""
    progress_list = await get_badge_progress(current_user.id, db)
    responses = []
    for item in progress_list:
        badge = item["badge"]
        threshold = item["threshold"]
        current_value = item["current_value"]

        if threshold and threshold > 0:
            progress_pct = min(100.0, round(current_value / threshold * 100, 1))
        else:
            progress_pct = 100.0 if item["earned"] else 0.0

        badge_resp = BadgeResponse.from_orm_with_url(badge)
        responses.append(
            BadgeProgressResponse(
                badge=badge_resp,
                earned=item["earned"],
                earned_at=item["earned_at"],
                current_value=current_value,
                threshold=threshold,
                progress_pct=progress_pct,
            )
        )
    return responses


@router.post(
    "/badges/check",
    response_model=NewlyEarnedBadgesResponse,
    summary="Check and award newly earned badges for current user",
    tags=["badges"],
)
async def check_badges(
    current_user=Depends(_get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NewlyEarnedBadgesResponse:
    """Check all badge criteria and award any newly earned badges to the current user."""
    newly_earned = await check_all_badges(current_user.id, db)

    # Count total earned badges
    total_result = await db.execute(
        select(Badge)
        .join(UserBadge, UserBadge.badge_id == Badge.id)
        .where(UserBadge.user_id == current_user.id)
    )
    total_earned = len(total_result.scalars().all())

    return NewlyEarnedBadgesResponse(
        newly_earned=[BadgeResponse.from_orm_with_url(b) for b in newly_earned],
        total_earned=total_earned,
    )
