"""
Application configuration loaded from environment variables / .env file.
"""

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Runtime settings for the Aurik backend.

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
        "postgresql+asyncpg://postgres:password@localhost:5432/aurik"
    )
    MAPBOX_TOKEN: str = ""

    # NPS API
    NPS_API_KEY: str = ""

    # Geocoding
    GEOCODING_USER_AGENT: str = "aurik/1.0"
    GEOCODING_RATE_LIMIT: float = 1.0  # seconds between requests

    # Scraper
    SCRAPER_TIMEOUT: float = 30.0
    SCRAPER_MAX_RETRIES: int = 3

    # Scoring
    SCORE_SEARCH_RADIUS_KM: float = 10.0

    # Groq LLM for Site Insight summaries (optional — set to enable)
    GROQ_API_KEY: str = ""  # falsy → LLM summary disabled, /score returns summary=None
    GROQ_MODEL: str = "llama-3.1-8b-instant"

    # Supabase Auth
    SUPABASE_JWT_SECRET: str = ""
    SUPABASE_URL: str = ""

    # Google OAuth2 (for Google Drive integration)
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/api/v1/google/callback"
    GOOGLE_TOKEN_ENCRYPTION_KEY: str = ""  # Fernet key for encrypting stored tokens

    # Frontend URL (used for OAuth redirects)
    FRONTEND_URL: str = "http://localhost:5173"

    # Stripe billing
    STRIPE_SECRET_KEY: str = ""
    STRIPE_PUBLISHABLE_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    STRIPE_PRICE_MONTHLY: str = ""   # Price ID for $4.99/mo
    STRIPE_PRICE_ANNUAL: str = ""    # Price ID for $49.99/yr

    @field_validator("SUPABASE_URL", "FRONTEND_URL")
    @classmethod
    def strip_trailing_slash(cls, v: str) -> str:
        return v.rstrip("/") if v else v


settings = Settings()
