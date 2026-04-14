"""
Disk-based cache for pre-computed semantic multipliers.

Stores {location_id: {multiplier, text_hash}} so restarting the server
does not re-run the HuggingFace model for unchanged locations.

Cache file: ~/.aurik/semantic_scores.json
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Cache file location
# ---------------------------------------------------------------------------

def _cache_path() -> Path:
    """Return the path to the semantic scores cache file."""
    env_path = os.environ.get("SEMANTIC_CACHE_PATH")
    if env_path:
        return Path(env_path)
    return Path.home() / ".aurik" / "semantic_scores.json"


# ---------------------------------------------------------------------------
# Hash helpers
# ---------------------------------------------------------------------------

def text_hash(name: str, description: str, location_type: str) -> str:
    """Return a 16-character SHA-256 hex digest of the location's text fields."""
    raw = f"{name}|{description}|{location_type}".encode()
    return hashlib.sha256(raw).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Cache I/O
# ---------------------------------------------------------------------------

def load_cache() -> dict:
    """
    Load the cache from disk.

    Returns an empty dict on any error (missing file, corrupt JSON, etc.).
    """
    path = _cache_path()
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        logger.debug("Loaded semantic cache from %s (%d entries)", path, len(data))
        return data
    except FileNotFoundError:
        logger.debug("Semantic cache not found at %s — starting empty.", path)
        return {}
    except Exception as exc:
        logger.debug("Failed to load semantic cache: %s — starting empty.", exc)
        return {}


def save_cache(cache: dict) -> None:
    """
    Atomically write the cache dict to disk.

    Uses a temp file + os.replace() so a crash during write never
    leaves a corrupt cache file.  Silently ignores all errors.
    """
    path = _cache_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(cache, fh)
            os.replace(tmp_path, path)
        except Exception:
            # Clean up the temp file if something went wrong
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise
    except Exception as exc:
        logger.debug("Failed to save semantic cache: %s", exc)


# ---------------------------------------------------------------------------
# Public cache accessors
# ---------------------------------------------------------------------------

def get_cached(
    location_id: str,
    name: str,
    description: str,
    location_type: str,
) -> Optional[float]:
    """
    Return the cached multiplier for a location if it exists and is fresh.

    A cache entry is considered stale when the text hash no longer matches
    (i.e. the location's name / description / type has changed).

    Returns:
        The cached float multiplier, or None on a cache miss or stale entry.
    """
    entry = _cache.get(str(location_id))
    if entry is None:
        return None
    expected_hash = text_hash(name, description, location_type)
    if entry.get("hash") != expected_hash:
        return None
    return entry.get("multiplier")


def set_cached(
    location_id: str,
    name: str,
    description: str,
    location_type: str,
    multiplier: float,
) -> None:
    """
    Store a newly computed multiplier in the in-memory cache and persist to disk.
    """
    _cache[str(location_id)] = {
        "multiplier": multiplier,
        "hash": text_hash(name, description, location_type),
    }
    save_cache(_cache)


# ---------------------------------------------------------------------------
# Module-level cache loaded on import
# ---------------------------------------------------------------------------

_cache: dict = load_cache()
