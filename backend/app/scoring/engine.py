"""
Scoring engine helpers for metal-detecting site interest.

Provides type-weight constants and helper functions used by the
/hotspots endpoint.
"""

from __future__ import annotations

import math
from typing import Dict, Optional

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Base interest weight by location type
WEIGHTS: Dict[str, float] = {
    "battle": 80.0,
    "camp": 70.0,
    "railroad_stop": 60.0,
    "trail": 40.0,
    "town": 90.0,
    "mine": 75.0,
    "structure": 50.0,
    "event": 40.0,
    "church": 50.0,
    "school": 45.0,
    "cemetery": 55.0,
    "fairground": 75.0,
    "ferry": 70.0,
    "stagecoach_stop": 85.0,
    "spring": 35.0,
    "locale": 35.0,
    "mission": 80.0,
    "trading_post": 85.0,
    "pony_express": 85.0,
    "shipwreck": 60.0,
    "abandoned_church": 50.0,
    "historic_brothel": 65.0,
}

# Age decay / boost constants
_AGE_REFERENCE_YEAR = 1900
_MAX_AGE_BONUS = 20.0


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def _age_bonus(year: Optional[int]) -> float:
    """
    Return an additive age bonus based on how old the site is.

    Older sites (pre-1900) receive up to ``_MAX_AGE_BONUS`` points.
    Post-reference-year sites receive no bonus.
    """
    if year is None:
        return 0.0
    age = _AGE_REFERENCE_YEAR - year
    if age <= 0:
        return 0.0
    bonus = _MAX_AGE_BONUS * math.log1p(age) / math.log1p(500)
    return min(bonus, _MAX_AGE_BONUS)


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return the great-circle distance between two points in kilometres."""
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    )
    return R * 2 * math.asin(math.sqrt(a))
