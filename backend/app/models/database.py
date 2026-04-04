"""
SQLAlchemy async engine with PostGIS support.

Sets up the database connection, ORM models, and table creation
for the Prescia Maps historical intelligence system.
"""

import enum
import uuid
from typing import AsyncGenerator

from geoalchemy2 import Geometry
from sqlalchemy import (
    JSON,
    Column,
    Enum,
    Float,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

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


class LinearFeatureType(str, enum.Enum):
    """Supported linear geographic feature types."""

    trail = "trail"
    railroad = "railroad"


class MapLayerType(str, enum.Enum):
    """Supported map overlay types."""

    usgs = "usgs"
    railroad = "railroad"
    trail = "trail"
    mining = "mining"


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
    geom = Column(Geometry("POINT", srid=4326), nullable=True)


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
    geom = Column(Geometry("LINESTRING", srid=4326), nullable=True)
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
    """
    async with engine.begin() as conn:
        # Enable PostGIS extension (idempotent)
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
        # Create all tables defined in the ORM
        await conn.run_sync(Base.metadata.create_all)
