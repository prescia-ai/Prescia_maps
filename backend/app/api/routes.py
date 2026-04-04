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
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from geoalchemy2.functions import ST_Buffer, ST_DWithin, ST_MakePoint, ST_SetSRID
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.database import LinearFeature, Location, get_db
from app.models.schemas import (
    GeoJSONFeatureCollection,
    HealthResponse,
    HeatmapPoint,
    LocationCreate,
    LocationResponse,
    ScoreResponse,
)
from app.scoring.engine import compute_heatmap_data, score_location

logger = logging.getLogger(__name__)

router = APIRouter()


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

        import json
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
    # Convert radius from km to degrees (approximate)
    radius_deg = radius_km / 111.0

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
        ST_DWithin(Location.geom, point_expr, radius_deg),
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
        ST_DWithin(LinearFeature.geom, point_expr, radius_deg),
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
    from geoalchemy2.functions import ST_MakePoint, ST_SetSRID

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
