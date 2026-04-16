"""
Scoring engine for metal-detecting site interest.

Computes a 0–100 composite score for any geographic coordinate based on
the proximity and type of nearby historical locations and linear features.
Also generates heatmap weight data for all locations in the database.
"""

from __future__ import annotations

import logging
import math
from typing import Any, Dict, List, Optional, Tuple

from app.scoring.semantic import batch_compute_semantic_scores

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
    "abandoned_church": 50.0, # Same family as church
    "historic_brothel": 65.0, # High commerce area, likely coin loss
}

# Human-readable labels for each location type (used in breakdown text)
_TYPE_LABELS: Dict[str, str] = {
    "town": "Old town site",
    "battle": "Battle site",
    "camp": "Historic camp",
    "mine": "Historic mine",
    "railroad_stop": "Railroad stop",
    "stagecoach_stop": "Stagecoach stop",
    "trading_post": "Trading post",
    "mission": "Historic mission",
    "cemetery": "Cemetery",
    "ferry": "Ferry crossing",
    "fairground": "Historic fairground",
    "church": "Historic church",
    "school": "Historic school",
    "spring": "Historic spring",
    "locale": "Historic locale",
    "structure": "Historic structure",
    "event": "Historic event",
    "pony_express": "Pony Express station",
    "shipwreck": "Shipwreck site",
    "abandoned_church": "Abandoned church",
    "historic_brothel": "Historic establishment",
}

# Modifiers (additive, applied before clamping)
NEAR_WATER_BONUS = 20.0
NEAR_INTERSECTION_BONUS = 30.0
OVERLAP_MULTIPLIER_PER_EXTRA = 0.15   # base bonus per additional site beyond the first

# Age decay / boost constants
# Sites older than this threshold get an age bonus proportional to age
_AGE_REFERENCE_YEAR = 1900
_MAX_AGE_BONUS = 20.0

# Distance decay: score contribution falls off as a Gaussian
# Tightened from 2.0 to 1.5 km — sites 6+ km away contribute very little
_DECAY_SIGMA_KM = 1.5

# Default confidence when the DB field is NULL
# Raised from 0.5 to 0.8 — most locations are reasonably well-documented
_DEFAULT_CONFIDENCE = 0.8

# Minimum semantic multiplier deviation to include in the score breakdown dict
_SEMANTIC_BREAKDOWN_THRESHOLD = 0.05

# Score compression threshold: raw scores above this value are soft-compressed
# Raised from 60 to 85 — lets the full 0-100 range be meaningful
# A Civil War battlefield + creek + railroad crossing SHOULD score 90+
_COMPRESSION_THRESHOLD = 85.0

# Maximum number of individual location entries shown in the score breakdown
_MAX_BREAKDOWN_ENTRIES = 8


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
    2. Apply an overlap multiplier (polynomial) when multiple sites overlap.
    3. Add bonuses for proximity to water (rivers/streams encoded as
       features with ``"water"`` in the name) and trail/railroad intersections.
    4. Soft-compress scores above 85 and clamp to [0, 100].

    Args:
        lat:               Query latitude.
        lon:               Query longitude.
        nearby_locations:  List of dicts with keys ``type``, ``latitude``,
                           ``longitude``, ``year`` (all from the DB).
        nearby_features:   List of dicts with keys ``type``, ``name`` for
                           nearby linear features.

    Returns:
        Dict with ``score`` (float), ``raw_score`` (float),
        ``breakdown`` (dict), and ``nearby_count`` (int).
    """
    breakdown: Dict[str, float] = {}
    raw_score = 0.0

    # --- Location contributions ---
    location_contributions: List[float] = []
    semantic_mults = batch_compute_semantic_scores(
        [{"name": loc.get("name", ""), "description": loc.get("description", ""), "type": loc.get("type", "event")}
         for loc in nearby_locations],
        location_ids=[str(loc.get("id", "")) for loc in nearby_locations],
    )

    # Track per-location entries for human-readable breakdown
    per_loc_entries: List[Tuple[str, float]] = []

    for i, loc in enumerate(nearby_locations):
        loc_type = loc.get("type", "event")
        base_weight = WEIGHTS.get(loc_type, WEIGHTS["event"])

        # Apply semantic relevance multiplier if name/description available
        name = loc.get("name", "").strip()
        semantic_mult = semantic_mults[i]
        if name:
            base_weight = base_weight * semantic_mult

        loc_lat = loc.get("latitude") or lat
        loc_lon = loc.get("longitude") or lon
        dist_km = _haversine_km(lat, lon, loc_lat, loc_lon)
        dist_factor = _distance_weight(dist_km)

        age_b = _age_bonus(loc.get("year"))
        confidence = float(loc.get("confidence") or _DEFAULT_CONFIDENCE)
        contribution = (base_weight + age_b) * dist_factor * confidence

        location_contributions.append(contribution)

        # Build human-readable breakdown key
        type_label = _TYPE_LABELS.get(loc_type, loc_type.replace("_", " ").title())
        year = loc.get("year")
        try:
            year_suffix = f", est. {int(year)}s" if year is not None and int(year) < 2000 else ""
        except (ValueError, TypeError):
            year_suffix = ""
        if name:
            breakdown_key = f"{name} ({type_label}{year_suffix}) — {dist_km:.1f}km"
        else:
            breakdown_key = f"{type_label}{year_suffix} — {dist_km:.1f}km"
        per_loc_entries.append((breakdown_key, contribution))

    # Add top-N location contributions to breakdown (sorted by contribution)
    per_loc_entries.sort(key=lambda x: -x[1])
    for key, val in per_loc_entries[:_MAX_BREAKDOWN_ENTRIES]:
        breakdown[key] = round(val, 1)

    if location_contributions:
        # Sum contributions with polynomial overlap multiplier
        # More aggressive compounding: 3+ sites compound stronger than linear
        base_sum = sum(location_contributions)
        n_extra = max(0, len(location_contributions) - 1)
        # Polynomial: each extra site adds base 15% + accelerating bonus
        overlap_boost = min(3.0, 1.0 + OVERLAP_MULTIPLIER_PER_EXTRA * n_extra + 0.03 * n_extra ** 2)
        raw_score += base_sum * overlap_boost

        # Add cluster bonus note to breakdown if 3+ sites
        if n_extra >= 2:
            breakdown["near_cluster"] = round((overlap_boost - 1.0) * base_sum, 1)

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

    # Soft-compress scores above threshold to prevent artificial ceiling
    if raw_score > _COMPRESSION_THRESHOLD:
        compressed = _COMPRESSION_THRESHOLD + (raw_score - _COMPRESSION_THRESHOLD) / (
            1 + (raw_score - _COMPRESSION_THRESHOLD) / _COMPRESSION_THRESHOLD
        )
    else:
        compressed = raw_score
    final_score = round(min(max(compressed, 0.0), 100.0), 2)
    breakdown["final_score"] = final_score

    return {
        "score": final_score,
        "raw_score": round(raw_score, 2),
        "breakdown": breakdown,
        "nearby_count": len(nearby_locations),
    }


def _cluster_points(raw_points: List[Dict[str, float]], cell_size_deg: float) -> List[Dict[str, float]]:
    """
    Grid-based clustering for low zoom levels.

    Aggregates nearby location weights into coarse grid cells to reveal
    broad regional hotspots without overwhelming detail.
    """
    cells: Dict[Tuple[int, int], float] = {}
    for p in raw_points:
        ci = math.floor(p["lat"] / cell_size_deg)
        cj = math.floor(p["lon"] / cell_size_deg)
        key = (ci, cj)
        cells[key] = cells.get(key, 0.0) + p["weight"]

    if not cells:
        return []

    max_w = max(cells.values())
    result: List[Dict[str, float]] = []
    for (ci, cj), w in cells.items():
        result.append({
            "lat": round((ci + 0.5) * cell_size_deg, 4),
            "lon": round((cj + 0.5) * cell_size_deg, 4),
            "weight": round(w / max_w, 4),
        })
    return result


def _interpolate_points(
    raw_points: List[Dict[str, float]],
    grid_spacing_deg: float,
    influence_deg: float,
) -> List[Dict[str, float]]:
    """
    Grid interpolation for mid zoom levels.

    Each location "bleeds" its weight into surrounding grid cells using
    Gaussian decay.  The area between two nearby historical sites will
    accumulate heat from both, creating a warm glow between them.
    """
    if not raw_points:
        return []

    cells: Dict[Tuple[int, int], float] = {}
    r_cells = math.ceil(influence_deg / grid_spacing_deg)
    sigma = influence_deg / 2.0

    for p in raw_points:
        gi = round(p["lat"] / grid_spacing_deg)
        gj = round(p["lon"] / grid_spacing_deg)

        for di in range(-r_cells, r_cells + 1):
            for dj in range(-r_cells, r_cells + 1):
                cell_lat = (gi + di) * grid_spacing_deg
                cell_lon = (gj + dj) * grid_spacing_deg
                dist_deg = math.sqrt(
                    (p["lat"] - cell_lat) ** 2 + (p["lon"] - cell_lon) ** 2
                )
                if dist_deg > influence_deg:
                    continue
                decay = math.exp(-0.5 * (dist_deg / sigma) ** 2)
                key = (gi + di, gj + dj)
                cells[key] = cells.get(key, 0.0) + p["weight"] * decay

    if not cells:
        return []

    max_w = max(cells.values())
    threshold = max_w * 0.04  # drop cells with less than 4% of the max weight

    result: List[Dict[str, float]] = []
    for (gi, gj), w in cells.items():
        if w < threshold:
            continue
        result.append({
            "lat": round(gi * grid_spacing_deg, 4),
            "lon": round(gj * grid_spacing_deg, 4),
            "weight": round(w / max_w, 4),
        })
    return result


def compute_heatmap_data(
    all_locations: List[Dict[str, Any]],
    zoom: int = 10,
) -> List[Dict[str, float]]:
    """
    Generate zoom-adaptive heatmap weight data from all known historical locations.

    Zoom behaviour:
    - **Low zoom (≤ 7, state level):** Grid clustering with coarse cells.
      Returns regional hotspot centers — fewer points, broad patterns.
    - **Mid zoom (8–12, county level):** Grid interpolation with Gaussian
      influence radius.  Each site "bleeds" heat into surrounding cells so
      the area between two old towns glows warm.
    - **High zoom (≥ 13, street level):** Raw location points — individual
      sites are precise, frontend handles tight radius rendering.

    Args:
        all_locations: List of dicts with at least ``type``, ``latitude``,
                       ``longitude``, and optionally ``year``.
        zoom:          Current map zoom level from the frontend.

    Returns:
        List of ``{lat, lon, weight}`` dicts suitable for a heatmap overlay.
    """
    raw_points: List[Dict[str, float]] = []
    semantic_mults = batch_compute_semantic_scores(
        [{"name": loc.get("name", ""), "description": loc.get("description", ""), "type": loc.get("type", "event")}
         for loc in all_locations],
        location_ids=[str(loc.get("id", "")) for loc in all_locations],
    )
    max_weight = 0.0
    for i, loc in enumerate(all_locations):
        lat = loc.get("latitude")
        lon = loc.get("longitude")
        if lat is None or lon is None:
            continue

        loc_type = loc.get("type", "event")
        base = WEIGHTS.get(loc_type, WEIGHTS["event"])
        age_b = _age_bonus(loc.get("year"))
        confidence = float(loc.get("confidence") or _DEFAULT_CONFIDENCE)
        weight = (base + age_b) * confidence

        if loc.get("name", ""):
            weight = weight * semantic_mults[i]

        raw_points.append({"lat": lat, "lon": lon, "weight": weight})
        if weight > max_weight:
            max_weight = weight

    if not raw_points:
        return []

    # Normalise raw weights to [0, 1] before zoom-adaptive processing
    for p in raw_points:
        p["weight"] = round(p["weight"] / max_weight, 4) if max_weight > 0 else 0.0

    if zoom <= 7:
        # State / national level — cluster into 0.5° cells (~55 km)
        return _cluster_points(raw_points, cell_size_deg=0.5)
    elif zoom <= 12:
        # County level — blend with 0.5° influence radius, 0.2° grid spacing
        return _interpolate_points(raw_points, grid_spacing_deg=0.2, influence_deg=0.5)
    else:
        # Street level — return raw points; frontend uses tight radius
        return raw_points
