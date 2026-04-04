"""
Async Wikipedia scraper for historical Civil War battles, ghost towns, and
historic trails.

Fetches three Wikipedia list pages, parses tables and list items with
BeautifulSoup, and enriches records with Nominatim geocoding where
explicit coordinates are absent.
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

import httpx
from bs4 import BeautifulSoup, Tag

from app.scrapers.normalizer import assign_confidence, clean_name, classify_event_type, normalize_year
from app.services import geocoding

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Target pages
# ---------------------------------------------------------------------------

WIKIPEDIA_PAGES: List[Dict[str, str]] = [
    {
        "url": "https://en.wikipedia.org/wiki/List_of_American_Civil_War_battles",
        "source": "wikipedia:civil_war_battles",
        "default_type": "battle",
    },
    {
        "url": "https://en.wikipedia.org/wiki/List_of_ghost_towns_in_the_United_States",
        "source": "wikipedia:ghost_towns",
        "default_type": "town",
    },
    {
        "url": "https://en.wikipedia.org/wiki/Historic_trails_in_the_United_States",
        "source": "wikipedia:historic_trails",
        "default_type": "trail",
    },
    {
        "url": "https://en.wikipedia.org/wiki/List_of_battles_of_the_American_Revolutionary_War",
        "source": "wikipedia:revolutionary_war_battles",
        "default_type": "battle",
    },
    {
        "url": "https://en.wikipedia.org/wiki/List_of_forts_in_the_United_States",
        "source": "wikipedia:forts",
        "default_type": "structure",
    },
    {
        "url": "https://en.wikipedia.org/wiki/List_of_ghost_towns_in_Colorado",
        "source": "wikipedia:ghost_towns_colorado",
        "default_type": "town",
    },
    {
        "url": "https://en.wikipedia.org/wiki/List_of_ghost_towns_in_California",
        "source": "wikipedia:ghost_towns_california",
        "default_type": "town",
    },
]

# Wikipedia DMS coordinate pattern  e.g. 39°48′N 77°14′W
_DMS_PATTERN = re.compile(
    r"(\d{1,3})°(\d{1,2})′?([NS])\s+(\d{1,3})°(\d{1,2})′?([EW])"
)
# Decimal coordinate pattern  e.g. 39.8, -77.23
_DECIMAL_PATTERN = re.compile(r"(-?\d{1,3}\.\d{2,})\s*,\s*(-?\d{1,3}\.\d{2,})")

_HEADERS = {
    "User-Agent": (
        "prescia_maps/1.0 (historical research bot; "
        "https://github.com/prescia/maps)"
    )
}


# ---------------------------------------------------------------------------
# Coordinate helpers
# ---------------------------------------------------------------------------

def _dms_to_decimal(degrees: str, minutes: str, direction: str) -> float:
    """Convert degrees + minutes + hemisphere to a signed decimal degree."""
    value = float(degrees) + float(minutes) / 60.0
    if direction in ("S", "W"):
        value = -value
    return round(value, 6)


def _extract_coords_from_text(text: str) -> Optional[Tuple[float, float]]:
    """
    Attempt to parse geographic coordinates from an arbitrary text string.

    Tries DMS notation first, then decimal notation.

    Returns:
        ``(latitude, longitude)`` or ``None``.
    """
    dms_match = _DMS_PATTERN.search(text)
    if dms_match:
        lat = _dms_to_decimal(dms_match.group(1), dms_match.group(2), dms_match.group(3))
        lon = _dms_to_decimal(dms_match.group(4), dms_match.group(5), dms_match.group(6))
        return lat, lon

    dec_match = _DECIMAL_PATTERN.search(text)
    if dec_match:
        return float(dec_match.group(1)), float(dec_match.group(2))

    return None


def _extract_coords_from_tag(tag: Tag) -> Optional[Tuple[float, float]]:
    """
    Look for coordinate data hidden in HTML micro-format spans.

    Wikipedia uses ``<span class="geo">`` and ``geo-dec`` / ``geo-dms``
    spans, as well as ``data-lat`` / ``data-lon`` attributes on various
    elements.
    """
    # geo microformat
    geo_span = tag.find("span", class_="geo")
    if geo_span:
        coords = _extract_coords_from_text(geo_span.get_text())
        if coords:
            return coords

    # data-lat / data-lon attributes
    for elem in tag.find_all(attrs={"data-lat": True, "data-lon": True}):
        try:
            return float(elem["data-lat"]), float(elem["data-lon"])
        except (ValueError, KeyError):
            pass

    # geo-dec span
    geo_dec = tag.find("span", class_="geo-dec")
    if geo_dec:
        coords = _extract_coords_from_text(geo_dec.get_text())
        if coords:
            return coords

    return None


# ---------------------------------------------------------------------------
# Page fetching
# ---------------------------------------------------------------------------

async def _fetch_page(client: httpx.AsyncClient, url: str) -> Optional[BeautifulSoup]:
    """
    Fetch a Wikipedia page and return a parsed BeautifulSoup object.

    Returns ``None`` on HTTP or network errors.
    """
    try:
        response = await client.get(url, headers=_HEADERS, follow_redirects=True)
        response.raise_for_status()
        return BeautifulSoup(response.text, "lxml")
    except httpx.HTTPError as exc:
        logger.error("Failed to fetch %s: %s", url, exc)
        return None


# ---------------------------------------------------------------------------
# Per-page parsers
# ---------------------------------------------------------------------------

def _parse_battles_page(soup: BeautifulSoup, source: str) -> List[Dict[str, Any]]:
    """
    Parse the Civil War battles list page.

    The page contains sortable wikitables with columns:
    Battle | Date | State | Result | Strength (Union/Conf.) | Casualties.
    We extract name, date/year, state (for geocoding), and coordinates.
    """
    records: List[Dict[str, Any]] = []
    tables = soup.find_all("table", class_="wikitable")

    for table in tables:
        rows = table.find_all("tr")
        for row in rows[1:]:  # skip header
            cells = row.find_all(["td", "th"])
            if not cells:
                continue

            name_cell = cells[0]
            name_link = name_cell.find("a")
            raw_name = (name_link.get_text() if name_link else name_cell.get_text()).strip()
            name = clean_name(raw_name)
            if not name:
                continue

            # Year from date column (index 1 if available)
            year_text = cells[1].get_text() if len(cells) > 1 else ""
            year = normalize_year(year_text)

            # State column for geocoding fallback (index 2)
            state_text = cells[2].get_text().strip() if len(cells) > 2 else ""

            # Try coordinates from the row HTML
            coords = _extract_coords_from_tag(row)

            records.append(
                {
                    "name": name,
                    "description": f"American Civil War battle. {year_text}".strip(),
                    "year": year,
                    "latitude": coords[0] if coords else None,
                    "longitude": coords[1] if coords else None,
                    "source": source,
                    "location_hint": f"{name}, {state_text}".strip(", "),
                    "default_type": "battle",
                }
            )

    logger.info("Parsed %d battle records", len(records))
    return records


def _parse_ghost_towns_page(soup: BeautifulSoup, source: str) -> List[Dict[str, Any]]:
    """
    Parse the ghost towns list page.

    The page is structured as state-based ``<h2>/<h3>`` sections each
    followed by ``<ul>`` lists.  Each ``<li>`` contains the town name,
    optionally a wikilink, and a short description.
    """
    records: List[Dict[str, Any]] = []
    current_state = ""

    content = soup.find("div", id="mw-content-text")
    if not content:
        return records

    for elem in content.find_all(["h2", "h3", "ul"]):
        if elem.name in ("h2", "h3"):
            heading_text = elem.get_text(strip=True).replace("[edit]", "").strip()
            if heading_text and not any(
                x in heading_text.lower()
                for x in ["see also", "reference", "external", "note", "content"]
            ):
                current_state = heading_text
            continue

        if elem.name == "ul":
            for li in elem.find_all("li", recursive=False):
                link = li.find("a")
                raw_name = (link.get_text() if link else li.get_text()).strip()
                raw_name = raw_name.split("–")[0].split("-")[0].strip()
                name = clean_name(raw_name)
                if not name or len(name) < 2:
                    continue

                description = li.get_text(separator=" ").strip()
                year = normalize_year(description)
                coords = _extract_coords_from_tag(li)

                records.append(
                    {
                        "name": name,
                        "description": description[:500],
                        "year": year,
                        "latitude": coords[0] if coords else None,
                        "longitude": coords[1] if coords else None,
                        "source": source,
                        "location_hint": (
                            f"{name}, {current_state}, United States"
                            if current_state else name
                        ),
                        "default_type": "town",
                    }
                )

    logger.info("Parsed %d ghost town records", len(records))
    return records


def _parse_trails_page(soup: BeautifulSoup, source: str) -> List[Dict[str, Any]]:
    """
    Parse the historic trails list page.

    The page uses a wikitable with columns: Name | Designated | Length |
    Location.  We capture name, designation year, and description.
    """
    records: List[Dict[str, Any]] = []
    tables = soup.find_all("table", class_="wikitable")

    for table in tables:
        rows = table.find_all("tr")
        for row in rows[1:]:
            cells = row.find_all(["td", "th"])
            if not cells:
                continue

            name_cell = cells[0]
            link = name_cell.find("a")
            raw_name = (link.get_text() if link else name_cell.get_text()).strip()
            name = clean_name(raw_name)
            if not name:
                continue

            year_text = cells[1].get_text().strip() if len(cells) > 1 else ""
            year = normalize_year(year_text)
            location_text = cells[3].get_text().strip() if len(cells) > 3 else ""

            coords = _extract_coords_from_tag(row)

            records.append(
                {
                    "name": name,
                    "description": f"Historic trail. Designated: {year_text}. {location_text}".strip(),
                    "year": year,
                    "latitude": coords[0] if coords else None,
                    "longitude": coords[1] if coords else None,
                    "source": source,
                    "location_hint": location_text or name,
                    "default_type": "trail",
                }
            )

    # Fallback: parse list items if no tables found
    if not records:
        for li in soup.find_all("li"):
            link = li.find("a")
            if not link:
                continue
            name = clean_name(link.get_text())
            if not name:
                continue
            description = li.get_text(separator=" ").strip()
            records.append(
                {
                    "name": name,
                    "description": description[:500],
                    "year": normalize_year(description),
                    "latitude": None,
                    "longitude": None,
                    "source": source,
                    "location_hint": name,
                    "default_type": "trail",
                }
            )

    logger.info("Parsed %d trail records", len(records))
    return records


def _parse_revolutionary_war_battles_page(
    soup: BeautifulSoup, source: str
) -> List[Dict[str, Any]]:
    """
    Parse the Revolutionary War battles list page.

    The page contains sortable wikitables similar to the Civil War battles
    page.  We reuse the same table-parsing logic but set the description
    prefix and default_type appropriately for Revolutionary War context.
    """
    records: List[Dict[str, Any]] = []
    tables = soup.find_all("table", class_="wikitable")

    for table in tables:
        rows = table.find_all("tr")
        for row in rows[1:]:  # skip header
            cells = row.find_all(["td", "th"])
            if not cells:
                continue

            name_cell = cells[0]
            name_link = name_cell.find("a")
            raw_name = (name_link.get_text() if name_link else name_cell.get_text()).strip()
            name = clean_name(raw_name)
            if not name:
                continue

            year_text = cells[1].get_text() if len(cells) > 1 else ""
            year = normalize_year(year_text)
            state_text = cells[2].get_text().strip() if len(cells) > 2 else ""
            coords = _extract_coords_from_tag(row)

            records.append(
                {
                    "name": name,
                    "description": f"American Revolutionary War battle. {year_text}".strip(),
                    "year": year,
                    "latitude": coords[0] if coords else None,
                    "longitude": coords[1] if coords else None,
                    "source": source,
                    "location_hint": f"{name}, {state_text}".strip(", "),
                    "default_type": "battle",
                }
            )

    logger.info("Parsed %d Revolutionary War battle records", len(records))
    return records


def _parse_forts_page(soup: BeautifulSoup, source: str) -> List[Dict[str, Any]]:
    """
    Parse the list of forts in the United States page.

    The page is organised as state-based sections with ``<ul>`` list items,
    each containing a fort name (often a wikilink) and a short description.
    """
    records: List[Dict[str, Any]] = []
    current_state = ""

    content = soup.find("div", id="mw-content-text")
    if not content:
        return records

    for elem in content.find_all(["h2", "h3", "ul"]):
        if elem.name in ("h2", "h3"):
            heading_text = elem.get_text(strip=True).replace("[edit]", "").strip()
            if heading_text and not any(
                x in heading_text.lower()
                for x in ["see also", "reference", "external", "note", "content"]
            ):
                current_state = heading_text
            continue

        if elem.name == "ul":
            for li in elem.find_all("li", recursive=False):
                link = li.find("a")
                raw_name = (link.get_text() if link else li.get_text()).strip()
                raw_name = raw_name.split("–")[0].split("-")[0].strip()
                name = clean_name(raw_name)
                if not name or len(name) < 2:
                    continue

                description = li.get_text(separator=" ").strip()
                year = normalize_year(description)
                coords = _extract_coords_from_tag(li)

                records.append(
                    {
                        "name": name,
                        "description": description[:500],
                        "year": year,
                        "latitude": coords[0] if coords else None,
                        "longitude": coords[1] if coords else None,
                        "source": source,
                        "location_hint": (
                            f"{name}, {current_state}, United States"
                            if current_state else name
                        ),
                        "default_type": "structure",
                    }
                )

    logger.info("Parsed %d fort records", len(records))
    return records


_PAGE_PARSERS = {
    "wikipedia:civil_war_battles": _parse_battles_page,
    "wikipedia:ghost_towns": _parse_ghost_towns_page,
    "wikipedia:historic_trails": _parse_trails_page,
    "wikipedia:revolutionary_war_battles": _parse_revolutionary_war_battles_page,
    "wikipedia:forts": _parse_forts_page,
    "wikipedia:ghost_towns_colorado": _parse_ghost_towns_page,
    "wikipedia:ghost_towns_california": _parse_ghost_towns_page,
}


# ---------------------------------------------------------------------------
# Geocoding enrichment
# ---------------------------------------------------------------------------

async def _enrich_with_geocoding(
    records: List[Dict[str, Any]],
    concurrency: int = 3,
) -> List[Dict[str, Any]]:
    """
    Fill in missing coordinates using Nominatim geocoding.

    To respect the 1 req/sec Nominatim policy, we use a semaphore to
    limit concurrent requests.  Records that still have no coordinates
    after geocoding are kept (they may be inserted with NULL geom).

    Args:
        records:     List of raw scraped record dicts.
        concurrency: Maximum simultaneous geocoding requests.

    Returns:
        The same list with ``latitude``/``longitude`` filled where possible.
    """
    sem = asyncio.Semaphore(concurrency)

    async def _geocode_one(record: Dict[str, Any]) -> Dict[str, Any]:
        if record.get("latitude") is not None and record.get("longitude") is not None:
            return record
        async with sem:
            hint = record.get("location_hint", record["name"])
            coords = await geocoding.geocode(hint)
            if coords:
                record["latitude"], record["longitude"] = coords
                logger.debug("Geocoded %r -> %s", hint, coords)
            return record

    return list(await asyncio.gather(*(_geocode_one(r) for r in records)))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def scrape_all(
    geocode_missing: bool = True,
    timeout: float = 30.0,
) -> List[Dict[str, Any]]:
    """
    Scrape all configured Wikipedia pages and return normalised records.

    Each returned record is a dict with keys:
    ``name``, ``description``, ``year``, ``latitude``, ``longitude``,
    ``source``, ``type``, ``confidence``.

    Args:
        geocode_missing: If ``True``, attempt to geocode records that lack
                         explicit coordinates (slower but more complete).
        timeout:         HTTP timeout in seconds.

    Returns:
        List of record dicts ready for database insertion.
    """
    all_records: List[Dict[str, Any]] = []

    async with httpx.AsyncClient(timeout=timeout) as client:
        for page_config in WIKIPEDIA_PAGES:
            url = page_config["url"]
            source = page_config["source"]
            logger.info("Fetching %s", url)

            soup = await _fetch_page(client, url)
            if soup is None:
                continue

            parser = _PAGE_PARSERS.get(source)
            if parser is None:
                logger.warning("No parser registered for source %r", source)
                continue

            records = parser(soup, source)
            all_records.extend(records)

    # Optionally fill coordinates via geocoding
    if geocode_missing:
        all_records = await _enrich_with_geocoding(all_records)

    # Final normalisation pass
    finalised: List[Dict[str, Any]] = []
    for rec in all_records:
        event_type = classify_event_type(rec["name"], rec.get("description", ""))
        # Prefer the default_type if the classifier falls back to "event"
        if event_type == "event":
            event_type = rec.get("default_type", "event")

        has_coords = (
            rec.get("latitude") is not None and rec.get("longitude") is not None
        )
        confidence = assign_confidence(
            source=rec.get("source", ""),
            has_coords=has_coords,
            has_year=rec.get("year") is not None,
        )

        finalised.append(
            {
                "name": rec["name"],
                "description": rec.get("description"),
                "year": rec.get("year"),
                "latitude": rec.get("latitude"),
                "longitude": rec.get("longitude"),
                "source": rec.get("source"),
                "type": event_type,
                "confidence": confidence,
            }
        )

    logger.info("Total records scraped and normalised: %d", len(finalised))
    return finalised
