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


class LinearFeatureType(str, enum.Enum):
    trail = "trail"
    railroad = "railroad"


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
# Health check schema
# ---------------------------------------------------------------------------

class HealthResponse(BaseModel):
    """Minimal health-check response."""

    status: Literal["ok", "degraded"] = "ok"
    database: bool
    version: str = "1.0.0"
