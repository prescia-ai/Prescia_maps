"""
SQLAlchemy async engine with PostGIS support.

Sets up the database connection, ORM models, and table creation
for the Aurik historical intelligence system.
"""

import enum
import uuid
from datetime import datetime, timezone
from typing import AsyncGenerator

from geoalchemy2 import Geometry
from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index as sa_Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, relationship

from app.config import settings


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class LocationType(str, enum.Enum):
    """Supported historical site/event categories."""

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
    """Supported linear geographic feature types."""

    trail = "trail"
    railroad = "railroad"
    water = "water"
    road = "road"


class HuntPlanStatus(str, enum.Enum):
    """Lifecycle status of a hunt plan."""

    idea = "idea"
    planned = "planned"
    done = "done"
    archived = "archived"


class MapLayerType(str, enum.Enum):
    """Supported map overlay types."""

    usgs = "usgs"
    railroad = "railroad"
    trail = "trail"
    mining = "mining"
    blm = "blm"


# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------

class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


# ---------------------------------------------------------------------------
# ORM Models
# ---------------------------------------------------------------------------

class Location(Base):
    """
    Point-based historical location (battle, town, mine, etc.).

    The ``geom`` column stores a PostGIS POINT in EPSG:4326 so that
    spatial queries (distance, buffer, intersection) can be performed
    directly in the database.
    """

    __tablename__ = "locations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(Text, nullable=False, index=True)
    type = Column(
        Enum(LocationType, name="location_type_enum"),
        nullable=False,
        index=True,
    )
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    year = Column(Integer, nullable=True)
    description = Column(Text, nullable=True)
    source = Column(Text, nullable=True)
    confidence = Column(Float, nullable=False, default=0.5)
    # PostGIS geometry stored as WGS-84 (SRID 4326)
    geom = Column(Geometry("POINT", srid=4326, spatial_index=True), nullable=True)


class LinearFeature(Base):
    """
    Line-based geographic feature such as a historic trail or railroad.

    ``geom`` is a PostGIS LINESTRING so the frontend can render actual
    paths and the scoring engine can query proximity to routes.
    """

    __tablename__ = "linear_features"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(Text, nullable=False, index=True)
    type = Column(
        Enum(LinearFeatureType, name="linear_feature_type_enum"),
        nullable=False,
        index=True,
    )
    geom = Column(Geometry("LINESTRING", srid=4326, spatial_index=True), nullable=True)
    source = Column(Text, nullable=True)


class MapLayer(Base):
    """
    External map tile/overlay layer metadata.

    Stores the URL and arbitrary JSON metadata for USGS, railroad,
    trail, and mining overlay layers consumed by the frontend.
    """

    __tablename__ = "map_layers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(Text, nullable=False)
    type = Column(
        Enum(MapLayerType, name="map_layer_type_enum"),
        nullable=False,
        index=True,
    )
    url = Column(Text, nullable=False)
    metadata_ = Column("metadata", JSON, nullable=True)


class LandAccessCache(Base):
    """
    Cached land-access classification for a PAD-US area.

    Stores the result of the tier-1 rule engine so that repeated lookups
    for the same area code are returned instantly without re-querying
    the PAD-US REST API.
    """

    __tablename__ = "land_access_cache"

    area_code = Column(String(50), primary_key=True)
    unit_name = Column(Text, nullable=True)
    managing_agency = Column(Text, nullable=True)
    designation = Column(Text, nullable=True)
    state = Column(String(2), nullable=True)
    gap_status = Column(Integer, nullable=True)
    status = Column(String(20), nullable=False)  # allowed, off_limits, private_permit, unsure
    confidence = Column(Float, nullable=False)
    reason = Column(Text, nullable=True)
    source = Column(String(20), nullable=False)  # rule_tier1, user_override
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class LandAccessOverride(Base):
    """
    User-submitted override for a PAD-US area classification.

    Overrides always take priority over the rule engine and cached results.
    """

    __tablename__ = "land_access_overrides"

    area_code = Column(String(50), primary_key=True)
    status = Column(String(20), nullable=False)  # allowed, off_limits
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class User(Base):
    """
    Authenticated user profile.

    ``supabase_id`` mirrors the ``sub`` claim from the Supabase JWT so that
    incoming requests can be quickly matched to a local profile row.
    """

    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    supabase_id = Column(String(255), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False)
    username = Column(String(50), unique=True, nullable=True)
    display_name = Column(String(100), nullable=True)
    bio = Column(Text, nullable=True)
    location = Column(String(100), nullable=True)
    privacy = Column(String(20), default="public")
    is_admin = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Google OAuth2 integration
    google_refresh_token = Column(Text, nullable=True)  # Encrypted refresh token
    google_connected_at = Column(DateTime(timezone=True), nullable=True)
    google_email = Column(String(255), nullable=True)  # The Google account email they connected
    google_folder_id = Column(String(255), nullable=True)  # Google Drive "Aurik" folder ID
    avatar_url = Column(String(500), nullable=True)  # Public Google Drive thumbnail URL

    # Subscription fields
    subscription_tier = Column(String(20), default="free", nullable=False, server_default="free")
    subscription_status = Column(String(20), default="none", nullable=False, server_default="none")
    subscription_provider = Column(String(20), default="none", nullable=False, server_default="none")
    subscription_plan = Column(String(20), nullable=True)
    trial_ends_at = Column(DateTime(timezone=True), nullable=True)
    current_period_end = Column(DateTime(timezone=True), nullable=True)
    canceled_at = Column(DateTime(timezone=True), nullable=True)
    stripe_customer_id = Column(String(100), nullable=True, index=True)
    stripe_subscription_id = Column(String(100), nullable=True, index=True)

    @property
    def is_pro(self) -> bool:
        """Return True when the user has an active Pro subscription."""
        if self.subscription_tier != "pro":
            return False
        if self.subscription_status in ("trialing", "active"):
            return True
        # Cancellations stay Pro until current_period_end
        if (
            self.subscription_status == "canceled"
            and self.current_period_end is not None
            and self.current_period_end > datetime.now(timezone.utc)
        ):
            return True
        return False

    badges = relationship("UserBadge", back_populates="user", lazy="select")


class UserPin(Base):
    """
    A user-logged metal detecting hunt (personal pin).

    Each hunt is a point on the map with a date, notes, time spent,
    finds count, and privacy setting.
    """

    __tablename__ = "user_pins"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    name = Column(String(200), nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    geom = Column(Geometry("POINT", srid=4326, spatial_index=True), nullable=True)
    hunt_date = Column(DateTime(timezone=True), nullable=False)
    time_spent = Column(String(50), nullable=True)
    notes = Column(Text, nullable=True)
    finds_count = Column(Integer, nullable=True)
    privacy = Column(String(20), default="public")
    search_pattern = Column(String(50), nullable=True)
    depth_inches = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class PinSubmission(Base):
    """
    Community-submitted historical pin awaiting admin review.

    Users submit candidate pins; admins review, edit, then approve or reject.
    Approved submissions are copied to the ``locations`` table with
    ``source = "community:{username}"``.
    """

    __tablename__ = "pin_submissions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    submitter_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    submitter_username = Column(String(50), nullable=True)
    name = Column(String(200), nullable=False)
    pin_type = Column(String(50), nullable=True)
    suggested_type = Column(String(100), nullable=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    date_era = Column(String(100), nullable=True)
    description = Column(Text, nullable=True)
    source_reference = Column(Text, nullable=True)
    tags = Column(Text, nullable=True)
    status = Column(String(20), default="pending", nullable=False, index=True)
    admin_notes = Column(Text, nullable=True)
    rejection_reason = Column(Text, nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    submitted_at = Column(DateTime(timezone=True), server_default=func.now())


class Post(Base):
    """
    A user-authored text post visible in the social feed.

    Privacy:
    - "public"    — appears in the Global feed and Home feeds of followers.
    - "followers" — appears only in the Home feeds of followers.
    - "private"   — visible only to the author.
    """

    __tablename__ = "posts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    author_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    content = Column(Text, nullable=False)
    privacy = Column(String(20), default="public", nullable=False)
    group_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class PostComment(Base):
    """A comment left on a Post by a user."""

    __tablename__ = "post_comments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    post_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    author_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class PostReaction(Base):
    """
    A themed reaction to a Post.

    Each user may have at most one reaction per post (enforced by the
    composite primary key on ``user_id`` + ``post_id``).

    ``reaction_type`` is one of: "gold", "bullseye", "shovel", "fire".
    """

    __tablename__ = "post_reactions"

    user_id = Column(UUID(as_uuid=True), primary_key=True)
    post_id = Column(UUID(as_uuid=True), primary_key=True, index=True)
    reaction_type = Column(String(20), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class UserFollow(Base):
    """
    A follow relationship between two users.

    ``follower_id`` follows ``following_id``.
    The composite primary key naturally enforces uniqueness.
    """

    __tablename__ = "user_follows"

    follower_id = Column(UUID(as_uuid=True), primary_key=True)
    following_id = Column(UUID(as_uuid=True), primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class PostImage(Base):
    """An image attached to a feed post, stored in the author's Google Drive."""

    __tablename__ = "post_images"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    post_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    drive_file_id = Column(String(255), nullable=False)
    url = Column(String(500), nullable=False)  # Public thumbnail URL
    position = Column(Integer, nullable=False, default=0)  # Ordering: 0, 1, 2, 3
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class PinImage(Base):
    """An image attached to a hunt pin, stored in the user's Google Drive."""

    __tablename__ = "pin_images"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pin_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    drive_file_id = Column(String(255), nullable=False)
    url = Column(String(500), nullable=False)  # Public thumbnail URL
    position = Column(Integer, nullable=False, default=0)  # Ordering: 0, 1, 2, 3
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class CollectionPhoto(Base):
    """A curated photo in a user's personal collection, stored in Google Drive."""

    __tablename__ = "collection_photos"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    drive_file_id = Column(String(255), nullable=False)
    url = Column(String(500), nullable=False)           # Public thumbnail URL
    caption = Column(Text, nullable=True)                # Optional description/caption
    find_type = Column(String(50), nullable=True, index=True)   # coin, button, bullet, jewelry, buckle, tool, token, relic, other
    material = Column(String(50), nullable=True, index=True)    # silver, gold, copper, brass, bronze, lead, iron, aluminum, nickel
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Group(Base):
    """A user-created group for collaborative metal detecting."""

    __tablename__ = "groups"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    slug = Column(String(100), nullable=False, unique=True, index=True)
    description = Column(Text, nullable=True)
    privacy = Column(String(10), nullable=False, default="public")  # "public" or "private"
    created_by = Column(UUID(as_uuid=True), nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=True, onupdate=func.now())


class GroupMember(Base):
    """Membership record linking a user to a group."""

    __tablename__ = "group_members"

    group_id = Column(UUID(as_uuid=True), primary_key=True)
    user_id = Column(UUID(as_uuid=True), primary_key=True)
    role = Column(String(15), nullable=False, default="member")    # "owner", "moderator", "member"
    status = Column(String(15), nullable=False, default="active")  # "active", "pending"
    joined_at = Column(DateTime, nullable=False, server_default=func.now())


class GroupEvent(Base):
    """An event created by a group moderator or owner."""

    __tablename__ = "group_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    group_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    created_by = Column(UUID(as_uuid=True), nullable=False)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    event_date = Column(DateTime, nullable=False)
    event_end_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=True, onupdate=func.now())


class GroupEventRsvp(Base):
    """RSVP record linking a user to a group event."""

    __tablename__ = "group_event_rsvps"

    event_id = Column(UUID(as_uuid=True), primary_key=True)
    user_id = Column(UUID(as_uuid=True), primary_key=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())


class Badge(Base):
    """
    Achievement badge definition.

    Each badge has a unique badge_id that matches the PNG filename in
    /frontend/public/badges/{badge_id}.png.
    """

    __tablename__ = "badges"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    badge_id = Column(String(100), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=False)
    category = Column(String(30), nullable=False, index=True)  # hunt_milestone, finds, sites, score
    criteria = Column(JSONB, nullable=False)  # e.g. {"type": "hunt_count", "threshold": 10}
    points = Column(Integer, nullable=False, default=0)
    rarity = Column(String(20), nullable=False, default="common")  # common, uncommon, rare, epic, legendary
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user_badges = relationship("UserBadge", back_populates="badge", lazy="select")


class UserBadge(Base):
    """
    A badge earned by a user.

    The unique constraint on (user_id, badge_id) ensures each user can
    earn each badge only once.
    """

    __tablename__ = "user_badges"
    __table_args__ = (UniqueConstraint("user_id", "badge_id", name="uq_user_badge"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    badge_id = Column(UUID(as_uuid=True), ForeignKey("badges.id", ondelete="CASCADE"), nullable=False, index=True)
    earned_at = Column(DateTime(timezone=True), server_default=func.now())
    progress = Column(JSONB, nullable=True)

    user = relationship("User", back_populates="badges", lazy="select")
    badge = relationship("Badge", back_populates="user_badges", lazy="select")


class Notification(Base):
    """
    An in-app notification delivered to a user.

    ``type`` describes the event (e.g. "like", "comment", "badge_earned",
    "submission_approved", "group_invite").  ``actor_id`` is the user who
    triggered the event; it is nullable for system-generated notifications
    such as badge awards.  ``ref_id`` is a generic string that points at
    the relevant entity (post UUID, badge UUID, group UUID, etc.).
    """

    __tablename__ = "notifications"
    __table_args__ = (
        # Primary query path: fetch a user's unread notifications sorted by time.
        sa_Index(
            "ix_notifications_user_read_created",
            "user_id",
            "read",
            "created_at",
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    type = Column(String(50), nullable=False)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    actor_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    ref_id = Column(String(255), nullable=True)
    read = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class HuntPlan(Base):
    """
    A user-private hunt plan with a drawn zone, metadata, and optional exports.

    ``area_geojson`` stores the full polygon/rectangle/circle GeoJSON drawn
    by the user. ``geom`` is the centroid point, auto-derived server-side
    from area_geojson on create/update. Clients never set geom directly.
    """

    __tablename__ = "hunt_plans"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    title = Column(String(200), nullable=False)
    planned_date = Column(DateTime(timezone=True), nullable=True)
    site_type = Column(String(20), nullable=True)  # dirt|beach|water|park|yard|club_hunt
    status = Column(Enum(HuntPlanStatus), nullable=False, default=HuntPlanStatus.idea)

    notes = Column(Text, nullable=True)
    geom = Column(Geometry("POINT", srid=4326, spatial_index=True), nullable=True)
    area_geojson = Column(JSONB, nullable=False)

    in_zone_markers = Column(JSONB, nullable=True)  # [{id, lat, lng, type, label, note}]
    gear_checklist = Column(JSONB, nullable=True)   # [{item, checked}]
    permission = Column(JSONB, nullable=True)        # {owner_name, contact, status, expiry, notes}
    view_snapshot = Column(JSONB, nullable=True)     # {center: [lat,lng], zoom, layers: {...}}
    photo_urls = Column(JSONB, nullable=True)        # [str] Google Drive URLs

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=True, onupdate=func.now())


# ---------------------------------------------------------------------------
# Engine & Session Factory
# ---------------------------------------------------------------------------

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency that yields an async database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def create_tables() -> None:
    """
    Create all database tables (and PostGIS extension) if they do not exist.

    Called during application startup via the FastAPI lifespan context.
    PostGIS must already be installed in the PostgreSQL cluster; we only
    ensure the extension is enabled in the target database.

    Also runs idempotent ALTER TYPE statements to add any new enum values
    that may have been introduced after the initial schema was created.
    """
    _new_location_types = [
        "mission",
        "trading_post",
        "shipwreck",
        "pony_express",
        "abandoned_church",
        "historic_brothel",
        "abandoned_fairground",
        "beach",
        "trail_landmark",
        "ccc_camp",
        "homestead_site",
        "wwii_training",
        "wwi_training",
        "pow_camp",
    ]
    _new_map_layer_types = ["blm"]

    async with engine.begin() as conn:
        # Enable PostGIS extension (idempotent)
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
        # Create all tables defined in the ORM
        await conn.run_sync(Base.metadata.create_all)
        # Add any new LocationType enum values (idempotent)
        for val in _new_location_types:
            await conn.execute(
                text(
                    f"ALTER TYPE location_type_enum ADD VALUE IF NOT EXISTS '{val}'"
                )
            )
        # Add any new MapLayerType enum values (idempotent)
        for val in _new_map_layer_types:
            await conn.execute(
                text(
                    f"ALTER TYPE map_layer_type_enum ADD VALUE IF NOT EXISTS '{val}'"
                )
            )
        # Add group_id column to posts table if it was created before groups feature
        await conn.execute(
            text("ALTER TABLE posts ADD COLUMN IF NOT EXISTS group_id UUID DEFAULT NULL")
        )
        await conn.execute(
            text("CREATE INDEX IF NOT EXISTS ix_posts_group_id ON posts (group_id)")
        )
        # Add find_type column to collection_photos if it was created before this feature
        await conn.execute(
            text("ALTER TABLE collection_photos ADD COLUMN IF NOT EXISTS find_type VARCHAR(50) DEFAULT NULL")
        )
        await conn.execute(
            text("CREATE INDEX IF NOT EXISTS ix_collection_photos_find_type ON collection_photos (find_type)")
        )
        # Add material column to collection_photos if it was created before this feature
        await conn.execute(
            text("ALTER TABLE collection_photos ADD COLUMN IF NOT EXISTS material VARCHAR(50) DEFAULT NULL")
        )
        await conn.execute(
            text("CREATE INDEX IF NOT EXISTS ix_collection_photos_material ON collection_photos (material)")
        )
