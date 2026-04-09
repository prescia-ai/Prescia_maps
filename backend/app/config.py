"""
Application configuration loaded from environment variables / .env file.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Runtime settings for the Prescia Maps backend.

    Values are read from environment variables first, then from a ``.env``
    file in the working directory (if present).
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    DATABASE_URL: str = (
        "postgresql+asyncpg://postgres:password@localhost:5432/prescia_maps"
    )
    MAPBOX_TOKEN: str = ""

    # NPS API
    NPS_API_KEY: str = ""

    # Geocoding
    GEOCODING_USER_AGENT: str = "prescia_maps/1.0"
    GEOCODING_RATE_LIMIT: float = 1.0  # seconds between requests

    # Scraper
    SCRAPER_TIMEOUT: float = 30.0
    SCRAPER_MAX_RETRIES: int = 3

    # Scoring
    SCORE_SEARCH_RADIUS_KM: float = 10.0

    # Semantic scoring
    SEMANTIC_SCORING_ENABLED: bool = False

    # Supabase Auth
    SUPABASE_JWT_SECRET: str = ""
    SUPABASE_URL: str = ""


settings = Settings()
