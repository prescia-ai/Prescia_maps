"""
Prescia Maps – FastAPI route definitions.

All routes are mounted under the ``/api/v1`` prefix defined in
``main.py``.  Each endpoint relies on an injected async SQLAlchemy
session (``db``) and, where appropriate, calls the scoring engine.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import Response

from app.models.database import (
    LinearFeature,
    Location,
    MapLayer,
    get_db,
)
from app.models.schemas import (
    FeatureResponse,
    GeoJSONFeatureCollection,
    HealthResponse,
    HeatmapPoint,
    HotspotCluster,
    LinearFeatureProperties,
    LineStringGeometry,
    LocationCreate,
    LocationProperties,
    LocationResponse,
    MapLayerCreate,
    MapLayerResponse,
    PointGeometry,
    ScoreResponse,
)
from app.scoring.engine import WEIGHTS, _age_bonus, compute_heatmap_data, score_location

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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
    limit: int = Query(1000, ge=1, le=10000),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> GeoJSONFeatureCollection:
    """
    Return all historical locations as a GeoJSON FeatureCollection.

    Supports optional filtering by ``type`` and ``source``.
    """
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
    response_model=None,
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a historical location",
    tags=["locations"],
)
async def delete_location(
    location_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
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
    db: AsyncSession = Depends(get_db),
) -> List[HeatmapPoint]:
    """
    Return weighted heatmap points for all historical locations.

    Each point's weight is normalised to [0, 1] and based on the
    location's type interest value and age.
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

    raw_points = compute_heatmap_data(all_locs)
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
    return ScoreResponse(
        lat=lat,
        lon=lon,
        score=result["score"],
        breakdown=result["breakdown"],
        nearby_count=result["nearby_count"],
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
    summary="Return the BLM public-lands tile URL and attribution",
    tags=["blm"],
)
async def get_blm_tile_url() -> Dict[str, str]:
    """
    Return the BLM (Bureau of Land Management) public-lands tile URL.

    The tile URL points to the BLM GeoCommunicator WMS service, which
    provides boundaries of federally managed public lands overlaid on the
    base map.
    """
    return {
        "url": (
            "https://gis.blm.gov/arcgis/rest/services/lands/BLM_Natl_SMA_Combined/MapServer/tile/{z}/{y}/{x}"
        ),
        "attribution": "Bureau of Land Management (BLM) – Public Domain",
    }


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