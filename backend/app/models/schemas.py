"""
Pydantic v2 schemas for request/response validation and serialisation.

Includes GeoJSON-compatible response models so the API can serve data
directly to mapping libraries (Mapbox GL JS, Leaflet, etc.).
"""

from __future__ import annotations

import enum
from typing import Any, Dict, List, Literal, Optional, Union
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ---------------------------------------------------------------------------
# Re-export enums for convenience
# ---------------------------------------------------------------------------

class LocationType(str, enum.Enum):
    battle = "battle"
    camp = "camp"
    railroad_stop = "railroad_stop"
    trail = "trail"
    town = "town"
    mine = "mine"
    structure = "structure"
    event = "event"
    church = "church"
    school = "school"
    cemetery = "cemetery"
    fairground = "fairground"
    ferry = "ferry"
    stagecoach_stop = "stagecoach_stop"
    spring = "spring"
    locale = "locale"
    mission = "mission"
    trading_post = "trading_post"
    shipwreck = "shipwreck"
    pony_express = "pony_express"


class LinearFeatureType(str, enum.Enum):
    trail = "trail"
    railroad = "railroad"
    water = "water"
    road = "road"


class MapLayerType(str, enum.Enum):
    usgs = "usgs"
    railroad = "railroad"
    trail = "trail"
    mining = "mining"


# ---------------------------------------------------------------------------
# Location Schemas
# ---------------------------------------------------------------------------

class LocationCreate(BaseModel):
    """Payload for creating a new historical location."""

    name: str = Field(..., min_length=1, max_length=512)
    type: LocationType
    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)
    year: Optional[int] = Field(None, ge=-5000, le=2100)
    description: Optional[str] = None
    source: Optional[str] = None
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class LocationResponse(BaseModel):
    """Full location record returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    type: LocationType
    latitude: float
    longitude: float
    year: Optional[int]
    description: Optional[str]
    source: Optional[str]
    confidence: float


# ---------------------------------------------------------------------------
# GeoJSON primitives
# ---------------------------------------------------------------------------

class PointGeometry(BaseModel):
    """GeoJSON Point geometry."""

    type: Literal["Point"] = "Point"
    coordinates: List[float] = Field(..., min_length=2, max_length=3)


class LineStringGeometry(BaseModel):
    """GeoJSON LineString geometry."""

    type: Literal["LineString"] = "LineString"
    coordinates: List[List[float]]


# ---------------------------------------------------------------------------
# GeoJSON Feature / FeatureCollection
# ---------------------------------------------------------------------------

class LocationProperties(BaseModel):
    """Properties block inside a GeoJSON Feature for a Location."""

    id: UUID
    name: str
    type: LocationType
    year: Optional[int]
    description: Optional[str]
    source: Optional[str]
    confidence: float


class LinearFeatureProperties(BaseModel):
    """Properties block inside a GeoJSON Feature for a LinearFeature."""

    id: UUID
    name: str
    type: LinearFeatureType
    source: Optional[str]


class FeatureResponse(BaseModel):
    """Generic GeoJSON Feature wrapper."""

    type: Literal["Feature"] = "Feature"
    geometry: Union[PointGeometry, LineStringGeometry]
    properties: Union[LocationProperties, LinearFeatureProperties]


class GeoJSONFeatureCollection(BaseModel):
    """GeoJSON FeatureCollection returned by /locations and /features."""

    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: List[FeatureResponse]


# ---------------------------------------------------------------------------
# Heatmap & Score schemas
# ---------------------------------------------------------------------------

class HeatmapPoint(BaseModel):
    """Single weighted point for the heatmap overlay."""

    lat: float
    lon: float
    weight: float = Field(..., ge=0.0)


class ScoreResponse(BaseModel):
    """
    Scoring result for a queried coordinate.

    ``score`` is a 0–100 float representing metal-detecting interest.
    ``breakdown`` maps contributing factor names to their numeric contribution.
    ``nearby_count`` is the number of historical sites within the search radius.
    """

    lat: float
    lon: float
    score: float = Field(..., ge=0.0, le=100.0)
    breakdown: Dict[str, float]
    nearby_count: int


# ---------------------------------------------------------------------------
# Map Layer Schemas
# ---------------------------------------------------------------------------

class MapLayerCreate(BaseModel):
    """Payload for registering a new map layer."""

    name: str = Field(..., min_length=1, max_length=256)
    type: MapLayerType
    url: str
    metadata: Optional[Dict[str, Any]] = None


class MapLayerResponse(BaseModel):
    """Map layer record returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    type: MapLayerType
    url: str
    metadata: Optional[Dict[str, Any]] = None


# ---------------------------------------------------------------------------
# Hotspot cluster schema
# ---------------------------------------------------------------------------

class HotspotCluster(BaseModel):
    """A spatial cluster of historical locations ranked by aggregate score."""

    cluster_id: int
    centroid_lat: float
    centroid_lon: float
    location_count: int
    aggregate_score: float
    types_present: List[str]
    top_locations: List[str]  # names of top 5 locations by weight


# ---------------------------------------------------------------------------
# Health check schema
# ---------------------------------------------------------------------------

class HealthResponse(BaseModel):
    """Minimal health-check response."""

    status: Literal["ok", "degraded"] = "ok"
    database: bool
    version: str = "1.0.0"


# ---------------------------------------------------------------------------
# Land Access schemas
# ---------------------------------------------------------------------------

class LandAccessResponse(BaseModel):
    """Full land-access classification for a PAD-US area."""

    area_code: str
    unit_name: Optional[str] = None
    managing_agency: Optional[str] = None
    designation: Optional[str] = None
    state: Optional[str] = None
    gap_status: Optional[int] = None
    status: str  # allowed, off_limits, private_permit, unsure
    confidence: float
    reason: Optional[str] = None
    source: str  # rule_tier1, cached, user_override
    last_verified: Optional[str] = None


class LandAccessOverrideCreate(BaseModel):
    """Payload for creating/updating a user override."""

    status: str = Field(..., pattern=r"^(allowed|off_limits)$")
    notes: Optional[str] = None


class LandAccessOverrideResponse(BaseModel):
    """User override record."""

    area_code: str
    status: str
    notes: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
