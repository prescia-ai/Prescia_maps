#!/usr/bin/env python3
"""
Google My Maps extractor — fetches pin data from any public Google My Maps
map and saves it as a JSON file ready for import into Aurik.

Two extraction modes:

1. **Online (default)** — fetches the viewer page for a given map ID, parses
   the embedded JavaScript data blobs that contain all placemark data, and
   saves the result.

2. **Offline / KML fallback** — parses a locally downloaded ``.kml`` or
   ``.kmz`` file when the viewer scrape fails or Google changes their page
   structure.

Usage::

    # Online (recommended)
    python scripts/fetch_google_my_maps.py \\
        --mid 1UUfwmW5YntQiVznItYrXwHYn1D9eGkgU \\
        --output-dir data/ \\
        --output-name frrandp_ghost_towns \\
        --type town \\
        --source frrandp_ghost_towns \\
        --confidence 0.80

    # KML / KMZ fallback
    python scripts/fetch_google_my_maps.py \\
        --file ghost_towns.kml \\
        --output-dir data/ \\
        --output-name frrandp_ghost_towns \\
        --type town \\
        --source frrandp_ghost_towns \\
        --confidence 0.80
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
import re
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional
from xml.etree import ElementTree as ET

import httpx

logger = logging.getLogger("fetch_google_my_maps")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_VIEWER_URL = "https://www.google.com/maps/d/u/0/viewer?mid={mid}"
_BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)
_KML_NS = "http://www.opengis.net/kml/2.2"

# Heuristic search window sizes used when parsing the viewer page HTML
_LOOKBACK_CHARS = 500   # characters before a coord pair to search for names
_LOOKAHEAD_CHARS = 1000  # characters after a coord pair to search for descriptions

# Length bounds for candidate name / description strings
_NAME_MIN_LEN = 2
_NAME_MAX_LEN = 120
_DESC_MIN_LEN = 5
_DESC_MAX_LEN = 300

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------


def _setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s  %(name)s  %(message)s",
        stream=sys.stderr,
    )


# ---------------------------------------------------------------------------
# Method 1 — scrape the viewer page
# ---------------------------------------------------------------------------


def fetch_viewer_html(mid: str) -> str:
    """Fetch the Google My Maps viewer page HTML for *mid*."""
    url = _VIEWER_URL.format(mid=mid)
    logger.info("Fetching viewer page: %s", url)
    headers = {"User-Agent": _BROWSER_UA}
    with httpx.Client(follow_redirects=True, timeout=30) as client:
        response = client.get(url, headers=headers)
    response.raise_for_status()
    return response.text


def _extract_strings_near_coords(html: str) -> List[Dict[str, Any]]:
    """
    Heuristic extraction: scan the page for floating-point coordinate pairs
    that look like ``[null,null,<lat>,<lon>]`` and attempt to recover the
    place-name that appears nearby in the same JS array structure.

    Returns a list of raw dicts with keys: name, latitude, longitude,
    description (may be empty string).
    """
    results: List[Dict[str, Any]] = []

    # Unescape common JS escape sequences so we can parse the text more easily
    text = html.replace(r"\x22", '"').replace(r"\x27", "'")
    # Also unescape hex-escaped brackets which Google uses heavily
    text = text.replace(r"\x5b", "[").replace(r"\x5d", "]")
    text = text.replace(r"\x3d", "=").replace(r"\x26", "&")

    # Pattern: [null,null,<lat>,<lon>] — typical Google My Maps coordinate entry
    coord_pattern = re.compile(
        r'\[null,null,(-?\d{1,3}\.\d{4,}),(-?\d{1,3}\.\d{4,})\]'
    )
    name_pattern = re.compile(rf'"([^"]{{{_NAME_MIN_LEN},{_NAME_MAX_LEN}}})"')
    desc_pattern = re.compile(rf'"([^"]{{{_DESC_MIN_LEN},{_DESC_MAX_LEN}}})"')

    for m in coord_pattern.finditer(text):
        lat = float(m.group(1))
        lon = float(m.group(2))

        # Validate coordinate ranges
        if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
            continue

        # Look backwards for a JSON-style quoted string that is plausibly a
        # place name (non-empty, not a URL, not a hex blob).
        before = text[max(0, m.start() - _LOOKBACK_CHARS): m.start()]
        name_candidates = name_pattern.findall(before)
        name = ""
        for candidate in reversed(name_candidates):
            # Skip obvious non-names
            if re.search(r'https?://', candidate):
                continue
            if re.search(r'\\u[0-9a-fA-F]{4}', candidate):
                continue
            if len(candidate.split()) > 10:
                continue
            name = candidate
            break

        # Look for a description string after the coordinates
        after = text[m.end(): m.end() + _LOOKAHEAD_CHARS]
        desc_candidates = desc_pattern.findall(after)
        description = ""
        for candidate in desc_candidates:
            if re.search(r'https?://', candidate):
                continue
            if candidate == name:
                continue
            description = candidate
            break

        if name:
            results.append(
                {
                    "name": name,
                    "latitude": lat,
                    "longitude": lon,
                    "description": description,
                }
            )

    # Deduplicate by (name, lat, lon) — keep first occurrence
    seen: set = set()
    deduped: List[Dict[str, Any]] = []
    for entry in results:
        key = (entry["name"], entry["latitude"], entry["longitude"])
        if key not in seen:
            seen.add(key)
            deduped.append(entry)

    return deduped


def parse_viewer_html(html: str) -> List[Dict[str, Any]]:
    """
    Attempt to extract placemark data from a Google My Maps viewer page.

    Returns a list of raw dicts with keys: name, latitude, longitude,
    description.

    Raises ``ValueError`` if no pins could be extracted.
    """
    results = _extract_strings_near_coords(html)
    if not results:
        raise ValueError(
            "Could not parse map data from viewer page. "
            "Try downloading the KML manually and using --file instead."
        )
    return results


# ---------------------------------------------------------------------------
# Method 2 — parse a local KML / KMZ file
# ---------------------------------------------------------------------------


def _read_kml_bytes(path: Path) -> bytes:
    """Return the raw KML bytes from a .kml or .kmz file."""
    if path.suffix.lower() == ".kmz":
        with zipfile.ZipFile(path) as zf:
            kml_names = [n for n in zf.namelist() if n.endswith(".kml")]
            if not kml_names:
                raise ValueError(f"No .kml file found inside {path}")
            return zf.read(kml_names[0])
    return path.read_bytes()


def parse_kml_file(path: Path) -> List[Dict[str, Any]]:
    """
    Parse a local KML or KMZ file and return a list of raw dicts with keys:
    name, latitude, longitude, description.
    """
    logger.info("Parsing KML/KMZ file: %s", path)
    kml_bytes = _read_kml_bytes(path)

    # Strip leading BOM if present
    if kml_bytes.startswith(b"\xef\xbb\xbf"):
        kml_bytes = kml_bytes[3:]

    root = ET.fromstring(kml_bytes.decode("utf-8", errors="replace"))

    # Support both namespaced and non-namespaced KML
    ns_prefix = f"{{{_KML_NS}}}"
    tag_names = {el.tag for el in root.iter()}
    use_ns = any(t.startswith(ns_prefix) for t in tag_names)
    ns = {"kml": _KML_NS} if use_ns else {}

    placemark_path = ".//kml:Placemark" if use_ns else ".//Placemark"
    name_tag = "kml:name" if use_ns else "name"
    desc_tag = "kml:description" if use_ns else "description"
    coords_path = ".//kml:coordinates" if use_ns else ".//coordinates"

    results: List[Dict[str, Any]] = []
    for pm in root.findall(placemark_path, ns):
        name_el = pm.find(name_tag, ns)
        coords_el = pm.find(coords_path, ns)
        if name_el is None or coords_el is None:
            continue

        name = (name_el.text or "").strip()
        coords_text = (coords_el.text or "").strip()
        if not name or not coords_text:
            continue

        # KML coordinate format: lon,lat[,alt]
        parts = coords_text.split(",")
        if len(parts) < 2:
            continue
        try:
            lon = float(parts[0].strip())
            lat = float(parts[1].strip())
        except ValueError:
            logger.warning("Could not parse coordinates for %r: %s", name, coords_text)
            continue

        if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
            logger.warning("Out-of-range coordinates for %r: lat=%s lon=%s", name, lat, lon)
            continue

        desc_el = pm.find(desc_tag, ns)
        description = (desc_el.text or "").strip() if desc_el is not None else ""

        results.append(
            {
                "name": name,
                "latitude": lat,
                "longitude": lon,
                "description": description,
            }
        )

    if not results:
        raise ValueError(f"No valid Placemark entries found in {path}")

    return results


# ---------------------------------------------------------------------------
# Normalise to import format
# ---------------------------------------------------------------------------


def normalise(
    raw: List[Dict[str, Any]],
    location_type: str,
    source: str,
    confidence: float,
) -> List[Dict[str, Any]]:
    """Convert raw extracted records to the Aurik import format."""
    out: List[Dict[str, Any]] = []
    for entry in raw:
        record: Dict[str, Any] = {
            "name": entry["name"],
            "type": location_type,
            "latitude": entry["latitude"],
            "longitude": entry["longitude"],
            "source": source,
            "confidence": confidence,
        }
        if entry.get("description"):
            record["description"] = entry["description"]
        out.append(record)
    return out


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Extract pin data from a public Google My Maps map and save as "
            "JSON ready for import into Aurik."
        )
    )
    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument(
        "--mid",
        metavar="MAP_ID",
        help="Google My Maps map ID (online scraping mode).",
    )
    source_group.add_argument(
        "--file",
        metavar="PATH",
        type=Path,
        help="Path to a locally downloaded .kml or .kmz file (offline mode).",
    )
    parser.add_argument(
        "--output-dir",
        metavar="DIR",
        type=Path,
        default=Path("data/"),
        help="Directory to write output files (default: data/).",
    )
    parser.add_argument(
        "--output-name",
        metavar="NAME",
        default="google_my_maps_export",
        help="Base name for output files (default: google_my_maps_export).",
    )
    parser.add_argument(
        "--type",
        metavar="LOCATION_TYPE",
        dest="location_type",
        default="town",
        help="LocationType to assign to all pins (default: town).",
    )
    parser.add_argument(
        "--source",
        default="google_my_maps",
        help="Source string for all records (default: google_my_maps).",
    )
    parser.add_argument(
        "--confidence",
        type=float,
        default=0.80,
        help="Confidence value 0–1 for all records (default: 0.80).",
    )
    return parser


def main() -> None:
    _setup_logging()
    parser = _build_arg_parser()
    args = parser.parse_args()

    output_dir: Path = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    raw_path = output_dir / f"{args.output_name}_raw.json"
    out_path = output_dir / f"{args.output_name}.json"

    # ------------------------------------------------------------------
    # Extract raw data
    # ------------------------------------------------------------------
    raw: List[Dict[str, Any]] = []

    if args.mid:
        try:
            html = fetch_viewer_html(args.mid)
            raw = parse_viewer_html(html)
            logger.info("Extracted %d pins from viewer page.", len(raw))
        except Exception as exc:
            logger.error("Online extraction failed: %s", exc)
            logger.error(
                "Could not parse map data from viewer page. "
                "Try downloading the KML manually and using --file instead."
            )
            sys.exit(1)
    else:
        file_path: Path = args.file
        if not file_path.exists():
            logger.error("File not found: %s", file_path)
            sys.exit(1)
        try:
            raw = parse_kml_file(file_path)
            logger.info("Extracted %d pins from KML/KMZ file.", len(raw))
        except Exception as exc:
            logger.error("KML extraction failed: %s", exc)
            sys.exit(1)

    # ------------------------------------------------------------------
    # Save raw output
    # ------------------------------------------------------------------
    with open(raw_path, "w", encoding="utf-8") as fh:
        json.dump(raw, fh, indent=2, ensure_ascii=False)
    logger.info("Raw data saved → %s", raw_path)

    # ------------------------------------------------------------------
    # Normalise and save import-ready output
    # ------------------------------------------------------------------
    normalised = normalise(raw, args.location_type, args.source, args.confidence)
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(normalised, fh, indent=2, ensure_ascii=False)
    logger.info("Import-ready data saved → %s", out_path)

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    print(f"\nDone. {len(normalised)} pins extracted.")
    print(f"  Raw data   : {raw_path}")
    print(f"  Import file: {out_path}")


if __name__ == "__main__":
    main()
