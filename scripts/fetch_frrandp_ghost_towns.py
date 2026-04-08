#!/usr/bin/env python3
"""
Fetch FRRandP ghost towns GeoJSON from MapHub and save to the data/ directory.

Downloads the ghost towns GeoJSON from ``https://maphub.net/frrandp/ghost-towns``
(with several slug variations as fallbacks), saves the raw GeoJSON, and also
produces a normalised JSON array in the app's location import format.

Usage::

    # Default — saves to data/
    python scripts/fetch_frrandp_ghost_towns.py

    # Custom output directory
    python scripts/fetch_frrandp_ghost_towns.py --output-dir /tmp/ghost_towns

    # Override the MapHub URL directly
    python scripts/fetch_frrandp_ghost_towns.py --url https://maphub.net/frrandp/my-map/geojson
"""

from __future__ import annotations

import io
import sys

# Force UTF-8 output on Windows to prevent emoji/unicode crashes
if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if sys.stderr.encoding != "utf-8":
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import argparse
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger("fetch_frrandp_ghost_towns")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_USER_AGENT = (
    "prescia_maps/1.0 (historical research; "
    "https://github.com/prescia-ai/Prescia_maps)"
)

_MAPHUB_URL_CANDIDATES = [
    "https://maphub.net/frrandp/ghost-towns/geojson",
    "https://maphub.net/frrandp/Ghost-Towns/geojson",
    "https://maphub.net/frrandp/ghost-towns-map/geojson",
    "https://maphub.net/frrandp/Ghost-Towns-Map/geojson",
]

_RAW_FILENAME = "frrandp_ghost_towns_raw.geojson"
_NORMALIZED_FILENAME = "frrandp_ghost_towns.json"

_SOURCE = "frrandp_ghost_towns"
_CONFIDENCE = 0.80
_TYPE = "town"


# ---------------------------------------------------------------------------
# Fetch
# ---------------------------------------------------------------------------


def fetch_geojson(urls: List[str]) -> Dict[str, Any]:
    """Try each URL in order and return the first successful GeoJSON response."""
    headers = {"User-Agent": _USER_AGENT}
    last_error: Optional[Exception] = None

    with httpx.Client(timeout=60, follow_redirects=True) as client:
        for url in urls:
            logger.info("Trying %s …", url)
            try:
                response = client.get(url, headers=headers)
                if response.status_code == 200:
                    logger.info("Got 200 from %s", url)
                    return response.json()
                logger.warning("  → HTTP %d, skipping.", response.status_code)
            except httpx.HTTPError as exc:
                logger.warning("  → Request failed: %s", exc)
                last_error = exc

    msg = "All MapHub URL candidates failed."
    if last_error:
        raise RuntimeError(msg) from last_error
    raise RuntimeError(msg)


# ---------------------------------------------------------------------------
# Validate
# ---------------------------------------------------------------------------


def validate_geojson(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Confirm data is a GeoJSON FeatureCollection and return the features list."""
    if data.get("type") != "FeatureCollection":
        raise ValueError(
            f"Expected GeoJSON type 'FeatureCollection', got {data.get('type')!r}"
        )
    features = data.get("features")
    if not isinstance(features, list):
        raise ValueError("GeoJSON 'features' field is missing or not a list.")
    logger.info("FeatureCollection contains %d features.", len(features))
    return features


# ---------------------------------------------------------------------------
# Convert
# ---------------------------------------------------------------------------


def _extract_name(props: Dict[str, Any]) -> Optional[str]:
    """Return the first non-empty name found in common property keys."""
    for key in ("name", "title", "Name"):
        value = props.get(key)
        if value and str(value).strip():
            return str(value).strip()
    return None


def _extract_description(props: Dict[str, Any]) -> Optional[str]:
    """Return the first non-empty description found in common property keys."""
    for key in ("description", "Description"):
        value = props.get(key)
        if value and str(value).strip():
            return str(value).strip()
    return None


def convert_features(
    features: List[Dict[str, Any]],
) -> tuple[List[Dict[str, Any]], int]:
    """
    Convert GeoJSON Point features to the app's location import format.

    Skips features that:
    - Are not Points
    - Have no name
    - Have no valid coordinates
    """
    locations: List[Dict[str, Any]] = []
    skipped = 0

    for feature in features:
        geometry = feature.get("geometry") or {}
        props = feature.get("properties") or {}

        # Only process Point geometries
        if geometry.get("type") != "Point":
            logger.debug("Skipping non-Point feature: type=%r", geometry.get("type"))
            skipped += 1
            continue

        coordinates = geometry.get("coordinates")
        if not coordinates or len(coordinates) < 2:
            logger.debug("Skipping feature with invalid coordinates: %r", coordinates)
            skipped += 1
            continue

        try:
            lon = float(coordinates[0])
            lat = float(coordinates[1])
        except (TypeError, ValueError):
            logger.debug("Skipping feature — coordinates not numeric: %r", coordinates)
            skipped += 1
            continue

        name = _extract_name(props)
        if not name:
            logger.debug("Skipping feature with no name; props=%r", props)
            skipped += 1
            continue

        record: Dict[str, Any] = {
            "name": name,
            "type": _TYPE,
            "latitude": lat,
            "longitude": lon,
            "source": _SOURCE,
            "confidence": _CONFIDENCE,
        }

        description = _extract_description(props)
        if description:
            record["description"] = description

        locations.append(record)

    return locations, skipped


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    parser = argparse.ArgumentParser(
        description=(
            "Fetch FRRandP ghost towns GeoJSON from MapHub and save "
            "to the data/ directory."
        )
    )
    parser.add_argument(
        "--output-dir",
        default="data/",
        help="Directory to write output files into (default: data/).",
    )
    parser.add_argument(
        "--url",
        default=None,
        help="Override the MapHub GeoJSON URL (skips the built-in candidate list).",
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Fetch
    # ------------------------------------------------------------------
    urls = [args.url] if args.url else _MAPHUB_URL_CANDIDATES
    geojson_data = fetch_geojson(urls)

    # ------------------------------------------------------------------
    # Validate
    # ------------------------------------------------------------------
    features = validate_geojson(geojson_data)
    total_raw = len(features)

    # ------------------------------------------------------------------
    # Save raw
    # ------------------------------------------------------------------
    raw_path = output_dir / _RAW_FILENAME
    with open(raw_path, "w", encoding="utf-8") as fh:
        json.dump(geojson_data, fh, ensure_ascii=False, indent=2)
    logger.info("Saved raw GeoJSON → %s", raw_path)

    # ------------------------------------------------------------------
    # Convert
    # ------------------------------------------------------------------
    locations, skipped = convert_features(features)
    total_converted = len(locations)

    # ------------------------------------------------------------------
    # Save normalized
    # ------------------------------------------------------------------
    normalized_path = output_dir / _NORMALIZED_FILENAME
    with open(normalized_path, "w", encoding="utf-8") as fh:
        json.dump(locations, fh, ensure_ascii=False, indent=2)
    logger.info("Saved normalized locations → %s", normalized_path)

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    logger.info(
        "Done. Raw features: %d | Converted: %d | Skipped: %d",
        total_raw,
        total_converted,
        skipped,
    )


if __name__ == "__main__":
    main()
