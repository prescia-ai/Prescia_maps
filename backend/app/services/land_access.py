"""
Land-access rule engine, PAD-US API client, and cache logic.

Classifies any PAD-US area into one of four statuses:
- ``allowed``       – public land where metal detecting is generally OK
- ``off_limits``    – detecting is prohibited or illegal
- ``private_permit``– private land, requires landowner permission
- ``unsure``        – rules vary; user should verify before going

Resolution order: User override → Cache → Tier-1 rule engine
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import LandAccessCache, LandAccessOverride

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Agency abbreviation mapping
# ---------------------------------------------------------------------------

_AGENCY_ABBREV: Dict[str, str] = {
    "BLM":  "BLM",
    "USFS": "USFS",
    "NPS":  "NPS",
    "FWS":  "FWS",
    "DOD":  "DOD",
    "BOR":  "BOR",
    "BIA":  "BIA",
}

_MANG_TYPE_ABBREV: Dict[str, str] = {
    "PVT":  "PVT",
    "TRIB": "TRIB",
    "LOC":  "LOC",
    "UNK":  "UNK",
}


def _agency_abbrev(mang_name: str, mang_type: str, des_tp: str) -> str:
    """Derive a short agency abbreviation from PAD-US attributes."""
    name_upper = (mang_name or "").upper()
    des_upper = (des_tp or "").upper()

    # Check explicit agency names first
    for key in ("BLM", "USFS", "NPS", "FWS", "DOD", "BOR", "BIA"):
        if key in name_upper:
            return key

    # Designation-based
    if "NATIONAL PARK" in des_upper:
        return "NPS"
    if "NATIONAL FOREST" in des_upper:
        return "USFS"
    if "WILDERNESS" in des_upper:
        return "WLD"
    if "STATE PARK" in des_upper:
        return "SP"
    if "STATE FOREST" in des_upper:
        return "SF"

    # Fall back to management type
    return _MANG_TYPE_ABBREV.get(mang_type or "", "UNK")


def _state_abbrev(state_nm: str) -> str:
    """Extract a 2-letter state abbreviation from PAD-US State_Nm."""
    _STATE_MAP: Dict[str, str] = {
        "ALABAMA": "AL", "ALASKA": "AK", "ARIZONA": "AZ", "ARKANSAS": "AR",
        "CALIFORNIA": "CA", "COLORADO": "CO", "CONNECTICUT": "CT",
        "DELAWARE": "DE", "FLORIDA": "FL", "GEORGIA": "GA", "HAWAII": "HI",
        "IDAHO": "ID", "ILLINOIS": "IL", "INDIANA": "IN", "IOWA": "IA",
        "KANSAS": "KS", "KENTUCKY": "KY", "LOUISIANA": "LA", "MAINE": "ME",
        "MARYLAND": "MD", "MASSACHUSETTS": "MA", "MICHIGAN": "MI",
        "MINNESOTA": "MN", "MISSISSIPPI": "MS", "MISSOURI": "MO",
        "MONTANA": "MT", "NEBRASKA": "NE", "NEVADA": "NV",
        "NEW HAMPSHIRE": "NH", "NEW JERSEY": "NJ", "NEW MEXICO": "NM",
        "NEW YORK": "NY", "NORTH CAROLINA": "NC", "NORTH DAKOTA": "ND",
        "OHIO": "OH", "OKLAHOMA": "OK", "OREGON": "OR", "PENNSYLVANIA": "PA",
        "RHODE ISLAND": "RI", "SOUTH CAROLINA": "SC", "SOUTH DAKOTA": "SD",
        "TENNESSEE": "TN", "TEXAS": "TX", "UTAH": "UT", "VERMONT": "VT",
        "VIRGINIA": "VA", "WASHINGTON": "WA", "WEST VIRGINIA": "WV",
        "WISCONSIN": "WI", "WYOMING": "WY", "DISTRICT OF COLUMBIA": "DC",
    }
    if not state_nm:
        return "XX"
    upper = state_nm.strip().upper()
    # Already a 2-letter code?
    if len(upper) == 2:
        return upper
    return _STATE_MAP.get(upper, "XX")


# ---------------------------------------------------------------------------
# Area-code generation
# ---------------------------------------------------------------------------

def generate_area_code(attrs: Dict[str, Any]) -> str:
    """
    Build a deterministic, human-readable area code:
    ``PADUS-{state_abbrev}-{agency_abbrev}-{OBJECTID}``
    """
    state = _state_abbrev(attrs.get("State_Nm", ""))
    agency = _agency_abbrev(
        attrs.get("Mang_Name", ""),
        attrs.get("Mang_Type", ""),
        attrs.get("Des_Tp", ""),
    )
    object_id = str(attrs.get("OBJECTID", "0")).zfill(4)
    return f"PADUS-{state}-{agency}-{object_id}"


# ---------------------------------------------------------------------------
# Tier-1 rule engine
# ---------------------------------------------------------------------------

def classify_area(attrs: Dict[str, Any]) -> Dict[str, Any]:
    """
    Deterministic classification of a PAD-US area.

    Returns ``{"status": ..., "confidence": ..., "reason": ...}``.
    """
    des_tp = (attrs.get("Des_Tp") or "").upper()
    mang_type = (attrs.get("Mang_Type") or "").upper()
    mang_name = (attrs.get("Mang_Name") or "").upper()
    gap_sts = attrs.get("GAP_Sts")
    try:
        gap_sts = int(gap_sts) if gap_sts is not None else None
    except (ValueError, TypeError):
        gap_sts = None

    # --- Wilderness (any agency) ---
    if "WILDERNESS" in des_tp:
        return {
            "status": "off_limits",
            "confidence": 0.98,
            "reason": "Wilderness Areas are federally protected; metal detecting is prohibited.",
        }

    # --- GAP Status 1 or 2 (any agency) ---
    if gap_sts in (1, 2):
        return {
            "status": "off_limits",
            "confidence": 0.90,
            "reason": f"GAP Status {gap_sts} indicates high protection — detecting is generally prohibited.",
        }

    # --- Federal agencies ---
    if mang_type == "FED" or any(a in mang_name for a in ("NPS", "FWS", "DOD", "BLM", "USFS", "BOR", "BIA")):
        # NPS
        if "NPS" in mang_name or "NATIONAL PARK" in des_tp:
            return {
                "status": "off_limits",
                "confidence": 0.98,
                "reason": "National Park Service lands — metal detecting is prohibited under the Archaeological Resources Protection Act.",
            }
        # Fish & Wildlife
        if "FWS" in mang_name or "FISH" in mang_name or "WILDLIFE" in des_tp:
            return {
                "status": "off_limits",
                "confidence": 0.95,
                "reason": "US Fish & Wildlife Service lands — metal detecting is prohibited.",
            }
        # DOD
        if "DOD" in mang_name or "DEFENSE" in mang_name or "MILITARY" in des_tp:
            return {
                "status": "off_limits",
                "confidence": 0.99,
                "reason": "Department of Defense land — access restricted; metal detecting is prohibited.",
            }
        # BLM with GAP 3
        if ("BLM" in mang_name or "BUREAU OF LAND MANAGEMENT" in mang_name) and gap_sts == 3:
            return {
                "status": "allowed",
                "confidence": 0.92,
                "reason": "BLM land with GAP Status 3 — metal detecting is generally allowed for recreational/hobby use.",
            }
        # BLM other
        if "BLM" in mang_name or "BUREAU OF LAND MANAGEMENT" in mang_name:
            return {
                "status": "allowed",
                "confidence": 0.85,
                "reason": "BLM land — metal detecting is generally allowed for recreational/hobby use. Check local restrictions.",
            }
        # USFS non-wilderness with GAP 3
        if ("USFS" in mang_name or "FOREST SERVICE" in mang_name or "NATIONAL FOREST" in des_tp) and gap_sts == 3:
            return {
                "status": "allowed",
                "confidence": 0.90,
                "reason": "USFS land (non-wilderness) with GAP Status 3 — metal detecting is generally allowed.",
            }
        # USFS other
        if "USFS" in mang_name or "FOREST SERVICE" in mang_name or "NATIONAL FOREST" in des_tp:
            return {
                "status": "allowed",
                "confidence": 0.80,
                "reason": "USFS land (non-wilderness) — metal detecting is generally allowed. Check local ranger district rules.",
            }
        # Bureau of Reclamation
        if "BOR" in mang_name or "RECLAMATION" in mang_name:
            return {
                "status": "unsure",
                "confidence": 0.50,
                "reason": "Bureau of Reclamation land — rules vary by site. Contact the local office before detecting.",
            }
        # BIA / Tribal
        if "BIA" in mang_name or "INDIAN AFFAIRS" in mang_name:
            return {
                "status": "unsure",
                "confidence": 0.30,
                "reason": "Bureau of Indian Affairs land — tribal sovereignty applies. Contact the tribal authority.",
            }

    # --- State lands ---
    if mang_type == "STAT":
        if "STATE FOREST" in des_tp or "STATE FOREST" in mang_name:
            return {
                "status": "allowed",
                "confidence": 0.80,
                "reason": "State forest land — metal detecting is generally allowed. Check state-specific rules.",
            }
        # State parks are unsure
        return {
            "status": "unsure",
            "confidence": 0.50,
            "reason": "State-managed land — rules vary by state and park. Contact the managing agency before detecting.",
        }

    # --- Tribal ---
    if mang_type == "TRIB":
        return {
            "status": "unsure",
            "confidence": 0.30,
            "reason": "Tribal land — tribal sovereignty applies. Contact the tribal authority before detecting.",
        }

    # --- Private ---
    if mang_type == "PVT" or gap_sts == 4:
        return {
            "status": "private_permit",
            "confidence": 0.85,
            "reason": "Private land — metal detecting requires landowner permission.",
        }

    # --- Local government ---
    if mang_type == "LOC":
        return {
            "status": "unsure",
            "confidence": 0.50,
            "reason": "Local government land — rules vary. Contact the local parks department before detecting.",
        }

    # --- Fallback ---
    return {
        "status": "unsure",
        "confidence": 0.40,
        "reason": "Unclassified public land — rules are unclear. Verify with the managing agency before detecting.",
    }


# ---------------------------------------------------------------------------
# PAD-US ArcGIS REST API client
# ---------------------------------------------------------------------------

PADUS_IDENTIFY_URL = (
    "https://gis.usgs.gov/arcgis/rest/services/PADUS3_0/MapServer/identify"
)


async def query_padus(lat: float, lon: float) -> Optional[Dict[str, Any]]:
    """
    Query the PAD-US ArcGIS REST identify endpoint for parcel attributes
    at the given lat/lon.  Returns the attribute dict of the first result,
    or ``None`` if nothing is found.
    """
    # Build a small bbox around the point for the mapExtent parameter
    delta = 0.01
    bbox = f"{lon - delta},{lat - delta},{lon + delta},{lat + delta}"

    params = {
        "geometry": f"{lon},{lat}",
        "geometryType": "esriGeometryPoint",
        "sr": "4326",
        "layers": "all",
        "tolerance": "2",
        "mapExtent": bbox,
        "imageDisplay": "800,600,96",
        "returnGeometry": "false",
        "f": "json",
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(PADUS_IDENTIFY_URL, params=params)
            resp.raise_for_status()
            data = resp.json()
    except Exception:
        logger.exception("PAD-US identify request failed for (%s, %s)", lat, lon)
        return None

    results = data.get("results")
    if not results:
        return None

    # Return the attributes of the first (most relevant) result
    return results[0].get("attributes")


# ---------------------------------------------------------------------------
# Main lookup function  (override → cache → rule engine)
# ---------------------------------------------------------------------------

async def lookup_land_access(
    lat: float,
    lon: float,
    db: AsyncSession,
) -> Dict[str, Any]:
    """
    Full resolution pipeline for a coordinate:
    1. Query PAD-US for parcel attributes
    2. Generate an area code
    3. Check user overrides
    4. Check cache
    5. Run tier-1 rule engine and cache result
    """

    # Step 1 — PAD-US attributes
    attrs = await query_padus(lat, lon)
    if attrs is None:
        # Not in PAD-US → private / unknown
        return {
            "area_code": f"PADUS-XX-UNK-0000",
            "unit_name": None,
            "managing_agency": None,
            "designation": None,
            "state": None,
            "gap_status": None,
            "status": "private_permit",
            "confidence": 0.85,
            "reason": "Location not found in PAD-US — assumed private land. Obtain landowner permission before detecting.",
            "source": "rule_tier1",
            "last_verified": datetime.now(timezone.utc).isoformat(),
        }

    # Step 2 — area code
    area_code = generate_area_code(attrs)

    # Step 3 — check user overrides
    override = await db.execute(
        select(LandAccessOverride).where(LandAccessOverride.area_code == area_code)
    )
    override_row = override.scalar_one_or_none()
    if override_row is not None:
        return {
            "area_code": area_code,
            "unit_name": attrs.get("Unit_Nm"),
            "managing_agency": attrs.get("Mang_Name"),
            "designation": attrs.get("Des_Tp"),
            "state": _state_abbrev(attrs.get("State_Nm", "")),
            "gap_status": attrs.get("GAP_Sts"),
            "status": override_row.status,
            "confidence": 1.0,
            "reason": f"User override: {override_row.notes or 'No notes provided.'}",
            "source": "user_override",
            "last_verified": (
                override_row.updated_at.isoformat()
                if override_row.updated_at
                else datetime.now(timezone.utc).isoformat()
            ),
        }

    # Step 4 — check cache
    cached = await db.execute(
        select(LandAccessCache).where(LandAccessCache.area_code == area_code)
    )
    cached_row = cached.scalar_one_or_none()
    if cached_row is not None:
        return {
            "area_code": cached_row.area_code,
            "unit_name": cached_row.unit_name,
            "managing_agency": cached_row.managing_agency,
            "designation": cached_row.designation,
            "state": cached_row.state,
            "gap_status": cached_row.gap_status,
            "status": cached_row.status,
            "confidence": cached_row.confidence,
            "reason": cached_row.reason,
            "source": "cached",
            "last_verified": (
                cached_row.updated_at.isoformat()
                if cached_row.updated_at
                else datetime.now(timezone.utc).isoformat()
            ),
        }

    # Step 5 — Tier-1 rule engine
    classification = classify_area(attrs)
    state_abbr = _state_abbrev(attrs.get("State_Nm", ""))

    # Step 6 — cache the result
    cache_entry = LandAccessCache(
        area_code=area_code,
        unit_name=attrs.get("Unit_Nm"),
        managing_agency=attrs.get("Mang_Name"),
        designation=attrs.get("Des_Tp"),
        state=state_abbr,
        gap_status=attrs.get("GAP_Sts"),
        status=classification["status"],
        confidence=classification["confidence"],
        reason=classification["reason"],
        source="rule_tier1",
        latitude=lat,
        longitude=lon,
    )
    db.add(cache_entry)
    try:
        await db.flush()
    except Exception:
        # Possible duplicate key if concurrent request cached same area
        await db.rollback()
        logger.debug("Cache entry for %s already exists (race condition).", area_code)

    return {
        "area_code": area_code,
        "unit_name": attrs.get("Unit_Nm"),
        "managing_agency": attrs.get("Mang_Name"),
        "designation": attrs.get("Des_Tp"),
        "state": state_abbr,
        "gap_status": attrs.get("GAP_Sts"),
        "status": classification["status"],
        "confidence": classification["confidence"],
        "reason": classification["reason"],
        "source": "rule_tier1",
        "last_verified": datetime.now(timezone.utc).isoformat(),
    }
