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
    abandoned_church = "abandoned_church"
    historic_brothel = "historic_brothel"
    abandoned_fairground = "abandoned_fairground"
    beach = "beach"
    trail_landmark = "trail_landmark"
    ccc_camp = "ccc_camp"
    homestead_site = "homestead_site"
    wwii_training = "wwii_training"
    wwi_training = "wwi_training"
    pow_camp = "pow_camp"


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
    blm = "blm"


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
    ``raw_score`` is the pre-compression score before the soft cap is applied.
    ``breakdown`` maps contributing factor names to their numeric contribution.
    ``nearby_count`` is the number of historical sites within the search radius.
    ``accessible`` is the land-access classification at the queried point
      (``'allowed'``, ``'off_limits'``, ``'private_permit'``, ``'unsure'``,
      or ``'unknown'`` when the lookup timed out or failed).
    """

    lat: float
    lon: float
    score: float = Field(..., ge=0.0, le=100.0)
    raw_score: Optional[float] = Field(None, ge=0.0)
    breakdown: Dict[str, float]
    nearby_count: int
    accessible: Optional[str] = None


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
# Import schemas
# ---------------------------------------------------------------------------

class ImportLocationItem(BaseModel):
    """A single location record for bulk import."""

    name: str = Field(..., min_length=1, max_length=512)
    type: LocationType
    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)
    year: Optional[int] = Field(None, ge=-5000, le=2100)
    description: Optional[str] = None
    source: Optional[str] = None
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class ImportFeatureItem(BaseModel):
    """A single GeoJSON Feature for linear feature import."""

    type: Literal["Feature"] = "Feature"
    geometry: LineStringGeometry
    properties: Dict[str, Any]


class ImportFeaturesRequest(BaseModel):
    """GeoJSON FeatureCollection wrapper for linear feature bulk import."""

    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: List[ImportFeatureItem]


class ImportSummaryResponse(BaseModel):
    """Summary returned after a bulk import operation."""

    inserted: int
    skipped_duplicate: int
    skipped_invalid: int
    errors: List[str]


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


# ---------------------------------------------------------------------------
# User / Auth schemas
# ---------------------------------------------------------------------------

class UserProfile(BaseModel):
    """Full user profile returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    supabase_id: str
    email: str
    username: Optional[str] = None
    display_name: Optional[str] = None
    bio: Optional[str] = None
    location: Optional[str] = None
    privacy: str = "public"
    created_at: Optional[Any] = None
    google_email: Optional[str] = None
    google_connected_at: Optional[Any] = None
    google_folder_id: Optional[str] = None
    avatar_url: Optional[str] = None
    is_admin: bool = False
    # Subscription info
    subscription_tier: str = "free"
    subscription_status: str = "none"
    is_pro: bool = False
    trial_ends_at: Optional[Any] = None


class UserProfileSetup(BaseModel):
    """Request model for first-time profile setup (username required)."""

    username: str = Field(..., min_length=3, max_length=30, pattern=r"^[a-zA-Z0-9_]+$")
    display_name: Optional[str] = Field(None, max_length=100)
    bio: Optional[str] = None
    location: Optional[str] = Field(None, max_length=100)


class UserProfileUpdate(BaseModel):
    """Request model for updating profile fields (all optional)."""

    display_name: Optional[str] = Field(None, max_length=100)
    bio: Optional[str] = None
    location: Optional[str] = Field(None, max_length=100)
    privacy: Optional[Literal["public", "friends", "private"]] = None


class UserProfilePublic(BaseModel):
    """Public profile fields — safe to expose to any viewer."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    username: Optional[str] = None
    display_name: Optional[str] = None
    bio: Optional[str] = None
    location: Optional[str] = None
    privacy: str = "public"
    created_at: Optional[Any] = None
    followers_count: int = 0
    following_count: int = 0
    is_following: bool = False
    avatar_url: Optional[str] = None
    is_admin: bool = False
    contributed_pins_count: int = 0


class UserSearchResult(BaseModel):
    """Minimal user info returned by the search endpoint."""

    username: str
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None


class UserProfileLimited(BaseModel):
    """Limited profile for private accounts — only basic identity fields."""

    model_config = ConfigDict(from_attributes=True)

    username: Optional[str] = None
    display_name: Optional[str] = None
    privacy: str = "private"
    created_at: Optional[Any] = None


# ---------------------------------------------------------------------------
# UserPin schemas
# ---------------------------------------------------------------------------

class UserPinCreate(BaseModel):
    """Request payload for logging a new hunt pin."""

    name: str = Field(..., min_length=1, max_length=200)
    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)
    hunt_date: str
    time_spent: Optional[str] = None
    notes: Optional[str] = Field(None, max_length=500)
    finds_count: Optional[int] = Field(None, ge=0)
    privacy: Optional[Literal["public", "friends", "private"]] = "public"
    search_pattern: Optional[str] = Field(None, max_length=50)
    depth_inches: Optional[int] = Field(None, ge=0)


class UserPinUpdate(BaseModel):
    """Request payload for updating an existing hunt pin (all fields optional)."""

    name: Optional[str] = Field(None, min_length=1, max_length=200)
    latitude: Optional[float] = Field(None, ge=-90.0, le=90.0)
    longitude: Optional[float] = Field(None, ge=-180.0, le=180.0)
    hunt_date: Optional[str] = None
    time_spent: Optional[str] = None
    notes: Optional[str] = Field(None, max_length=500)
    finds_count: Optional[int] = Field(None, ge=0)
    privacy: Optional[Literal["public", "friends", "private"]] = None
    search_pattern: Optional[str] = Field(None, max_length=50)
    depth_inches: Optional[int] = Field(None, ge=0)


class UserPinResponse(BaseModel):
    """Full hunt pin record returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    name: str
    latitude: float
    longitude: float
    hunt_date: Optional[Any] = None
    time_spent: Optional[str] = None
    notes: Optional[str] = None
    finds_count: Optional[int] = None
    privacy: str = "public"
    search_pattern: Optional[str] = None
    depth_inches: Optional[int] = None
    created_at: Optional[Any] = None
    images: List["PinImageResponse"] = Field(default_factory=list)


class UserPinListResponse(BaseModel):
    """Paginated list of hunt pins."""

    pins: List[UserPinResponse]
    total: int


# ---------------------------------------------------------------------------
# PinSubmission schemas
# ---------------------------------------------------------------------------

class PinSubmissionCreate(BaseModel):
    """Request model for creating a community pin submission."""

    name: str = Field(..., min_length=1, max_length=200)
    pin_type: Optional[str] = None
    suggested_type: Optional[str] = Field(None, max_length=100)
    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)
    date_era: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    source_reference: Optional[str] = None
    tags: Optional[str] = None


class PinSubmissionResponse(BaseModel):
    """Full pin submission record returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    submitter_id: UUID
    submitter_username: Optional[str] = None
    name: str
    pin_type: Optional[str] = None
    suggested_type: Optional[str] = None
    latitude: float
    longitude: float
    date_era: Optional[str] = None
    description: Optional[str] = None
    source_reference: Optional[str] = None
    tags: Optional[str] = None
    status: str
    admin_notes: Optional[str] = None
    rejection_reason: Optional[str] = None
    reviewed_at: Optional[Any] = None
    submitted_at: Optional[Any] = None


class PinSubmissionAdminUpdate(BaseModel):
    """Request model for admin edits on a submission."""

    name: Optional[str] = Field(None, max_length=200)
    pin_type: Optional[str] = None
    suggested_type: Optional[str] = Field(None, max_length=100)
    latitude: Optional[float] = Field(None, ge=-90.0, le=90.0)
    longitude: Optional[float] = Field(None, ge=-180.0, le=180.0)
    date_era: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None
    source_reference: Optional[str] = None
    tags: Optional[str] = None
    admin_notes: Optional[str] = None
    rejection_reason: Optional[str] = None
    status: Optional[Literal["pending", "approved", "rejected"]] = None


class PinSubmissionListResponse(BaseModel):
    """Paginated list of pin submissions."""

    submissions: List[PinSubmissionResponse]
    total: int


# ---------------------------------------------------------------------------
# Post / Feed schemas
# ---------------------------------------------------------------------------

REACTION_TYPES = {"gold", "bullseye", "shovel", "fire"}


class PostImageResponse(BaseModel):
    """Image attached to a post."""

    id: UUID
    url: str
    position: int


class PinImageResponse(BaseModel):
    """Image attached to a hunt pin."""

    id: UUID
    url: str
    position: int


class PostCreate(BaseModel):
    """Request payload for creating a new feed post."""

    content: str = Field(..., min_length=1, max_length=1000)
    privacy: Optional[Literal["public", "followers", "private"]] = "public"
    group_id: Optional[UUID] = None


class PostResponse(BaseModel):
    """Full post record with aggregated reaction counts and author info."""

    id: UUID
    author_id: UUID
    author_username: Optional[str] = None
    author_display_name: Optional[str] = None
    author_avatar_url: Optional[str] = None
    content: str
    privacy: str
    created_at: Optional[Any] = None
    comment_count: int = 0
    reactions: Dict[str, int] = Field(default_factory=lambda: {"gold": 0, "bullseye": 0, "shovel": 0, "fire": 0})
    my_reaction: Optional[str] = None
    images: List["PostImageResponse"] = Field(default_factory=list)
    group_id: Optional[UUID] = None
    group_name: Optional[str] = None
    group_slug: Optional[str] = None


class PostListResponse(BaseModel):
    """Paginated list of posts."""

    posts: List[PostResponse]
    total: int


class CommentCreate(BaseModel):
    """Request payload for creating a comment on a post."""

    content: str = Field(..., min_length=1, max_length=500)


class CommentResponse(BaseModel):
    """Comment record with author info."""

    id: UUID
    post_id: UUID
    author_id: UUID
    author_username: Optional[str] = None
    author_display_name: Optional[str] = None
    author_avatar_url: Optional[str] = None
    content: str
    created_at: Optional[Any] = None


class CommentListResponse(BaseModel):
    """Paginated list of comments."""

    comments: List[CommentResponse]
    total: int


class ReactRequest(BaseModel):
    """Request payload for reacting to a post."""

    reaction_type: Literal["gold", "bullseye", "shovel", "fire"]


# ---------------------------------------------------------------------------
# Follow schemas
# ---------------------------------------------------------------------------

class FollowInfo(BaseModel):
    """Minimal user info returned in follower/following lists."""

    user_id: UUID
    username: Optional[str] = None
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None


class FollowListResponse(BaseModel):
    """Paginated list of followers or following users."""

    users: List[FollowInfo]
    total: int


# ---------------------------------------------------------------------------
# Collection schemas
# ---------------------------------------------------------------------------

class CollectionPhotoResponse(BaseModel):
    """A single photo in a user's collection."""

    id: UUID
    user_id: UUID
    url: str
    caption: Optional[str] = None
    find_type: Optional[str] = None
    material: Optional[str] = None
    created_at: Optional[Any] = None


class CollectionPhotoListResponse(BaseModel):
    """Paginated list of collection photos."""

    photos: List[CollectionPhotoResponse]
    total: int


class CollectionPhotoUpdate(BaseModel):
    """Request payload for editing a collection photo's metadata."""

    caption: Optional[str] = Field(None, max_length=500)
    find_type: Optional[str] = Field(None, max_length=50)
    material: Optional[str] = Field(None, max_length=50)


# ---------------------------------------------------------------------------
# Group schemas
# ---------------------------------------------------------------------------

class GroupCreate(BaseModel):
    """Request payload for creating a new group."""

    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=1000)
    privacy: str = Field(default="public", pattern=r"^(public|private)$")


class GroupUpdate(BaseModel):
    """Request payload for updating group fields (all optional)."""

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=1000)
    privacy: Optional[str] = Field(None, pattern=r"^(public|private)$")


class GroupResponse(BaseModel):
    """Full group record returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    slug: str
    description: Optional[str]
    privacy: str
    created_by: UUID
    created_at: Any
    updated_at: Optional[Any] = None
    member_count: int = 0
    is_member: bool = False
    user_role: Optional[str] = None  # "owner", "moderator", "member", or None
    pending_request: bool = False


class GroupListResponse(BaseModel):
    """Paginated list of groups."""

    groups: List[GroupResponse]
    total: int


class GroupMemberResponse(BaseModel):
    """Member info returned in a group member list."""

    user_id: UUID
    username: Optional[str] = None
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    role: str
    joined_at: Any


class GroupMemberListResponse(BaseModel):
    """Paginated list of group members."""

    members: List[GroupMemberResponse]
    total: int


class GroupSearchResult(BaseModel):
    """Minimal group info returned by the search endpoint."""

    id: UUID
    name: str
    slug: str
    description: Optional[str] = None
    privacy: str
    member_count: int = 0


class GroupInvite(BaseModel):
    """Request payload for inviting a user to a group."""

    username: str


# ---------------------------------------------------------------------------
# Group Event schemas
# ---------------------------------------------------------------------------

class GroupEventCreate(BaseModel):
    """Request payload for creating a group event."""

    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)
    latitude: float
    longitude: float
    event_date: str  # ISO 8601 datetime string
    event_end_date: Optional[str] = None  # ISO 8601 datetime string


class GroupEventUpdate(BaseModel):
    """Request payload for updating a group event (all fields optional)."""

    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    event_date: Optional[str] = None
    event_end_date: Optional[str] = None


class GroupEventResponse(BaseModel):
    """Full group event record returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    group_id: UUID
    group_name: Optional[str] = None
    group_slug: Optional[str] = None
    created_by: UUID
    created_by_username: Optional[str] = None
    name: str
    description: Optional[str] = None
    latitude: float
    longitude: float
    event_date: Any
    event_end_date: Optional[Any] = None
    created_at: Any
    updated_at: Optional[Any] = None
    rsvp_count: int = 0
    user_has_rsvpd: bool = False


class GroupEventListResponse(BaseModel):
    """Paginated list of group events."""

    events: List[GroupEventResponse]
    total: int


class EventPinResponse(BaseModel):
    """Minimal event record for map pin display."""

    id: UUID
    group_id: UUID
    group_name: str
    group_slug: str
    name: str
    latitude: float
    longitude: float
    event_date: Any
    event_end_date: Optional[Any] = None
    rsvp_count: int = 0
    user_has_rsvpd: bool = False


# ---------------------------------------------------------------------------
# Badge schemas
# ---------------------------------------------------------------------------

class BadgeResponse(BaseModel):
    """Full badge definition returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    badge_id: str
    name: str
    description: str
    category: str
    criteria: Dict[str, Any]
    points: int
    rarity: str
    image_url: str = ""
    created_at: Optional[Any] = None

    @classmethod
    def from_orm_with_url(cls, badge: Any) -> "BadgeResponse":
        obj = cls.model_validate(badge)
        obj.image_url = f"/badges/{badge.badge_id}.png"
        return obj


class UserBadgeResponse(BaseModel):
    """A badge earned by a user, including badge details."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    badge_id: UUID
    earned_at: Optional[Any] = None
    badge: BadgeResponse


class BadgeProgressResponse(BaseModel):
    """Progress toward a badge for a user (earned or unearned)."""

    badge: BadgeResponse
    earned: bool
    earned_at: Optional[Any] = None
    current_value: int = 0
    threshold: Optional[int] = None
    progress_pct: float = 0.0


class NewlyEarnedBadgesResponse(BaseModel):
    """Response from the badge check endpoint."""

    newly_earned: List[BadgeResponse]
    total_earned: int


# ---------------------------------------------------------------------------
# Hunt Plan schemas
# ---------------------------------------------------------------------------

class HuntPlanStatus(str, enum.Enum):
    idea = "idea"
    planned = "planned"
    done = "done"
    archived = "archived"


class HuntPlanCreate(BaseModel):
    """Request payload for creating a new hunt plan."""

    title: str = Field(..., min_length=1, max_length=200)
    area_geojson: Dict[str, Any]
    planned_date: Optional[str] = None
    site_type: Optional[str] = Field(None, pattern=r"^(dirt|beach|water|park|yard|club_hunt)$")
    notes: Optional[str] = None
    in_zone_markers: Optional[List[Dict[str, Any]]] = None
    gear_checklist: Optional[List[Dict[str, Any]]] = None
    permission: Optional[Dict[str, Any]] = None
    view_snapshot: Optional[Dict[str, Any]] = None
    photo_urls: Optional[List[str]] = None


class HuntPlanUpdate(BaseModel):
    """Request payload for updating an existing hunt plan (all fields optional)."""

    title: Optional[str] = Field(None, min_length=1, max_length=200)
    area_geojson: Optional[Dict[str, Any]] = None
    planned_date: Optional[str] = None
    site_type: Optional[str] = Field(None, pattern=r"^(dirt|beach|water|park|yard|club_hunt)$")
    notes: Optional[str] = None
    in_zone_markers: Optional[List[Dict[str, Any]]] = None
    gear_checklist: Optional[List[Dict[str, Any]]] = None
    permission: Optional[Dict[str, Any]] = None
    view_snapshot: Optional[Dict[str, Any]] = None
    photo_urls: Optional[List[str]] = None


class HuntPlanResponse(BaseModel):
    """Full hunt plan record returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    owner_id: UUID
    title: str
    planned_date: Optional[Any] = None
    site_type: Optional[str] = None
    status: HuntPlanStatus
    notes: Optional[str] = None
    geom: Optional[Dict[str, float]] = None  # {lat, lng}
    area_geojson: Dict[str, Any]
    in_zone_markers: Optional[List[Dict[str, Any]]] = None
    gear_checklist: Optional[List[Dict[str, Any]]] = None
    permission: Optional[Dict[str, Any]] = None
    view_snapshot: Optional[Dict[str, Any]] = None
    photo_urls: Optional[List[str]] = None
    created_at: Optional[Any] = None
    updated_at: Optional[Any] = None


class HuntPlanListResponse(BaseModel):
    """Paginated list of hunt plans."""

    plans: List[HuntPlanResponse]
    total: int


class HuntPlanMapPin(BaseModel):
    """Lightweight plan record for map layer display."""

    id: UUID
    title: str
    lat: float
    lng: float
    status: HuntPlanStatus
    site_type: Optional[str] = None
    area_geojson: Optional[Dict[str, Any]] = None
    planned_date: Optional[str] = None
    notes_preview: Optional[str] = None


class HuntPlanStatusUpdate(BaseModel):
    """Request payload for changing a plan's status."""

    status: HuntPlanStatus


# ---------------------------------------------------------------------------
# Billing / Subscription schemas
# ---------------------------------------------------------------------------

class SubscriptionStatusResponse(BaseModel):
    """Current subscription status for the authenticated user."""

    model_config = ConfigDict(from_attributes=True)

    tier: str = "free"
    status: str = "none"
    plan: Optional[str] = None
    trial_ends_at: Optional[Any] = None
    current_period_end: Optional[Any] = None
    canceled_at: Optional[Any] = None
    is_pro: bool = False
    has_payment_method: bool = False


class CheckoutSessionRequest(BaseModel):
    """Request payload for creating a Stripe Checkout session."""

    plan: Literal["monthly", "annual"]
    success_url: str
    cancel_url: str


class CheckoutSessionResponse(BaseModel):
    """Response containing the Stripe Checkout URL."""

    checkout_url: str


class PortalSessionResponse(BaseModel):
    """Response containing the Stripe Billing Portal URL."""

    portal_url: str

