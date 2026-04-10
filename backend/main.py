"""
Prescia Maps – FastAPI application entry point.

Starts the async SQLAlchemy engine, registers all API routers, configures
CORS, and exposes the ASGI app for uvicorn.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.api.pins import router as pins_router
from app.api.submissions import router as submissions_router
from app.api.feed import router as feed_router
from app.api.social import router as social_router
from app.api.google_auth import router as google_auth_router
from app.auth.routes import router as auth_router
from app.models.database import create_tables

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan context manager.

    On startup:
    - Ensures the PostGIS extension is enabled.
    - Creates all ORM-defined tables if they do not exist.

    On shutdown:
    - Nothing extra required; SQLAlchemy disposes the engine automatically.
    """
    logger.info("Starting up – creating database tables …")
    await create_tables()
    logger.info("Database ready.")
    yield
    logger.info("Shutting down.")


# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------

def create_app() -> FastAPI:
    """
    Construct and configure the FastAPI application.

    Returns:
        Configured ``FastAPI`` instance.
    """
    app = FastAPI(
        title="Prescia Maps – Historical Activity Mapping & Metal Detecting Intelligence",
        description=(
            "REST API that aggregates historical location data (Civil War battles, "
            "ghost towns, historic trails, mines, camps) and computes scoring data "
            "for metal-detecting site research."
        ),
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # -----------------------------------------------------------------------
    # CORS
    # -----------------------------------------------------------------------
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # -----------------------------------------------------------------------
    # Routers
    # -----------------------------------------------------------------------
    app.include_router(router, prefix="/api/v1")
    app.include_router(pins_router, prefix="/api/v1")
    app.include_router(submissions_router, prefix="/api/v1")
    app.include_router(feed_router, prefix="/api/v1")
    app.include_router(social_router, prefix="/api/v1")
    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(google_auth_router, prefix="/api/v1")

    return app


app = create_app()


# ---------------------------------------------------------------------------
# Development entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
