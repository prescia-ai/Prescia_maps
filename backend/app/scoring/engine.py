"""
Scoring engine for metal-detecting site interest.

Computes a 0–100 composite score for any geographic coordinate based on
the proximity and type of nearby historical locations and linear features.
Also generates heatmap weight data for all locations in the database.
"""

from __future__ import annotations

import logging
import math
from typing import Any, Dict, List, Optional

from app.scoring.semantic import compute_semantic_score

logger = logging.getLogger(__name__)

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
    "cemetery": 55.0,       # cemeteries are high value for detecting
    "fairground": 75.0,
    "ferry": 70.0,          # ferry crossings = high coin loss
    "stagecoach_stop": 85.0, # highest value for detecting
    "spring": 35.0,
    "locale": 35.0,
    # New types from expanded data sources
    "mission": 80.0,         # Spanish missions = very high value
    "trading_post": 85.0,    # Trading posts = high commerce = high coin loss
    "pony_express": 85.0,    # Pony Express stations = documented high value
    "shipwreck": 60.0,       # River shipwrecks
}

# Modifiers (additive, applied before clamping)
NEAR_WATER_BONUS = 20.0
NEAR_INTERSECTION_BONUS = 30.0
OVERLAP_MULTIPLIER_PER_EXTRA = 0.15   # 15 % bonus per additional site beyond the first

# Age decay / boost constants
# Sites older than this threshold get an age bonus proportional to age
_AGE_REFERENCE_YEAR = 1900
_MAX_AGE_BONUS = 20.0

# Distance decay: score contribution falls off as 1/d² (softened)
_DECAY_SIGMA_KM = 2.0   # effective "radius" of influence

# Minimum semantic multiplier deviation to include in the score breakdown dict
_SEMANTIC_BREAKDOWN_THRESHOLD = 0.05


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Return the great-circle distance between two points in kilometres.

    Uses the haversine formula; accurate to ~0.5 % for short distances.
    """
    R = 6371.0  # Earth radius in km
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    )
    return R * 2 * math.asin(math.sqrt(a))


def _distance_weight(dist_km: float) -> float:
    """
    Gaussian-style decay weight in [0, 1] based on distance from the query point.

    At ``dist_km == 0`` the weight is 1.0; it drops to ~0.61 at ``_DECAY_SIGMA_KM``.
    """
    return math.exp(-0.5 * (dist_km / _DECAY_SIGMA_KM) ** 2)


def _age_bonus(year: Optional[int]) -> float:
    """
    Return an additive age bonus based on how old the site is.

    Older sites (pre-1900) receive up to ``_MAX_AGE_BONUS`` points.
    Post-reference-year sites receive no bonus.

    Args:
        year: Calendar year of the event (negative = BC).

    Returns:
        Float bonus in [0, _MAX_AGE_BONUS].
    """
    if year is None:
        return 0.0
    age = _AGE_REFERENCE_YEAR - year
    if age <= 0:
        return 0.0
    # Logarithmic scale capped at max
    bonus = _MAX_AGE_BONUS * math.log1p(age) / math.log1p(500)
    return min(bonus, _MAX_AGE_BONUS)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def score_location(
    lat: float,
    lon: float,
    nearby_locations: List[Dict[str, Any]],
    nearby_features: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Compute the metal-detecting interest score for a queried coordinate.

    Algorithm:
    1. For each nearby historical location, compute a distance-decayed
       contribution based on its type weight and age bonus.
    2. Apply an overlap multiplier when multiple sites overlap.
    3. Add bonuses for proximity to water (rivers/streams encoded as
       features with ``"water"`` in the name) and trail/railroad intersections.
    4. Clamp the final score to [0, 100].

    Args:
        lat:               Query latitude.
        lon:               Query longitude.
        nearby_locations:  List of dicts with keys ``type``, ``latitude``,
                           ``longitude``, ``year`` (all from the DB).
        nearby_features:   List of dicts with keys ``type``, ``name`` for
                           nearby linear features.

    Returns:
        Dict with ``score`` (float), ``breakdown`` (dict), and
        ``nearby_count`` (int).
    """
    breakdown: Dict[str, float] = {}
    raw_score = 0.0

    # --- Location contributions ---
    location_contributions: List[float] = []
    for loc in nearby_locations:
        loc_type = loc.get("type", "event")
        base_weight = WEIGHTS.get(loc_type, WEIGHTS["event"])

        # Apply semantic relevance multiplier if name/description available
        name = loc.get("name", "")
        description = loc.get("description", "")
        semantic_mult = 1.0
        if name:
            semantic_mult = compute_semantic_score(name, description, loc_type)
            base_weight = base_weight * semantic_mult

        loc_lat = loc.get("latitude") or lat
        loc_lon = loc.get("longitude") or lon
        dist_km = _haversine_km(lat, lon, loc_lat, loc_lon)
        dist_factor = _distance_weight(dist_km)

        age_b = _age_bonus(loc.get("year"))
        confidence = float(loc.get("confidence", 0.5))
        contribution = (base_weight + age_b) * dist_factor * confidence

        location_contributions.append(contribution)
        breakdown[f"loc:{loc.get('name', loc_type)[:30]}"] = round(contribution, 2)
        if name and abs(semantic_mult - 1.0) > _SEMANTIC_BREAKDOWN_THRESHOLD:
            breakdown[f"semantic:{name[:20]}"] = round(semantic_mult, 3)

    if location_contributions:
        # Sum contributions with overlap multiplier
        base_sum = sum(location_contributions)
        n_extra = max(0, len(location_contributions) - 1)
        overlap_boost = 1.0 + n_extra * OVERLAP_MULTIPLIER_PER_EXTRA
        raw_score += base_sum * overlap_boost
        breakdown["overlap_multiplier"] = round(overlap_boost, 3)

    # --- Linear feature bonuses ---
    feature_types = {f.get("type", "") for f in nearby_features}
    feature_names = " ".join(f.get("name", "").lower() for f in nearby_features)

    # Water proximity
    has_water = "water" in feature_types or any(
        kw in feature_names
        for kw in ["river", "creek", "stream", "lake", "pond", "bayou", "run"]
    )
    if has_water:
        raw_score += NEAR_WATER_BONUS
        breakdown["near_water"] = NEAR_WATER_BONUS

    # Trail / railroad intersection
    has_trail = "trail" in feature_types
    has_railroad = "railroad" in feature_types
    if has_trail and has_railroad:
        raw_score += NEAR_INTERSECTION_BONUS
        breakdown["near_intersection"] = NEAR_INTERSECTION_BONUS
    elif has_trail or has_railroad:
        bonus = NEAR_INTERSECTION_BONUS / 2
        raw_score += bonus
        breakdown["near_route"] = bonus

    final_score = round(min(max(raw_score, 0.0), 100.0), 2)
    breakdown["final_score"] = final_score

    return {
        "score": final_score,
        "breakdown": breakdown,
        "nearby_count": len(nearby_locations),
    }


def compute_heatmap_data(
    all_locations: List[Dict[str, Any]],
) -> List[Dict[str, float]]:
    """
    Generate heatmap weight data from all known historical locations.

    Each location contributes a point at its own coordinates weighted by
    its type base weight and age bonus, scaled to [0, 1].

    Args:
        all_locations: List of dicts with at least ``type``, ``latitude``,
                       ``longitude``, and optionally ``year``.

    Returns:
        List of ``{lat, lon, weight}`` dicts suitable for a heatmap overlay.
    """
    points: List[Dict[str, float]] = []
    max_weight = 0.0

    raw_points: List[Dict[str, float]] = []
    for loc in all_locations:
        lat = loc.get("latitude")
        lon = loc.get("longitude")
        if lat is None or lon is None:
            continue

        loc_type = loc.get("type", "event")
        base = WEIGHTS.get(loc_type, WEIGHTS["event"])
        age_b = _age_bonus(loc.get("year"))
        confidence = float(loc.get("confidence", 0.5))
        weight = (base + age_b) * confidence

        # Semantic multiplier for heatmap weighting
        name = loc.get("name", "")
        description = loc.get("description", "")
        if name:
            semantic_mult = compute_semantic_score(name, description, loc_type)
            weight = weight * semantic_mult

        raw_points.append({"lat": lat, "lon": lon, "weight": weight})
        if weight > max_weight:
            max_weight = weight

    # Normalise weights to [0, 1]
    for pt in raw_points:
        normalised = round(pt["weight"] / max_weight, 4) if max_weight > 0 else 0.0
        points.append({"lat": pt["lat"], "lon": pt["lon"], "weight": normalised})

    return points
