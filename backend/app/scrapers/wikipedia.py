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

from app.scrapers.normalizer import assign_confidence, clean_name, classify_event_type, normalize_year, is_blocked
from app.services import geocoding
from app.services import wiki_geocoding

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
        "url": "https://en.wikipedia.org/wiki/Historic_trails_and_roads_in_the_United_States",
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
    # Stagecoach
    {
        "url": "https://en.wikipedia.org/wiki/Butterfield_Overland_Mail",
        "source": "wikipedia:stagecoach_butterfield",
        "default_type": "stagecoach_stop",
    },
    {
        "url": "https://en.wikipedia.org/wiki/Overland_Mail_Company",
        "source": "wikipedia:stagecoach_overland",
        "default_type": "stagecoach_stop",
    },
    {
        "url": "https://en.wikipedia.org/wiki/Central_Overland_California_and_Pikes_Peak_Express_Company",
        "source": "wikipedia:stagecoach_central",
        "default_type": "stagecoach_stop",
    },
    # Pony Express
    {
        "url": "https://en.wikipedia.org/wiki/Pony_Express",
        "source": "wikipedia:pony_express",
        "default_type": "pony_express",
    },
    # Wagon trails
    {
        "url": "https://en.wikipedia.org/wiki/Oregon_Trail",
        "source": "wikipedia:oregon_trail",
        "default_type": "trail",
    },
    {
        "url": "https://en.wikipedia.org/wiki/California_Trail",
        "source": "wikipedia:california_trail",
        "default_type": "trail",
    },
    {
        "url": "https://en.wikipedia.org/wiki/Mormon_Trail",
        "source": "wikipedia:mormon_trail",
        "default_type": "trail",
    },
    {
        "url": "https://en.wikipedia.org/wiki/Santa_Fe_Trail",
        "source": "wikipedia:santa_fe_trail",
        "default_type": "trail",
    },
    {
        "url": "https://en.wikipedia.org/wiki/El_Camino_Real_de_Tierra_Adentro",
        "source": "wikipedia:el_camino_real",
        "default_type": "trail",
    },
    # Lewis & Clark
    {
        "url": "https://en.wikipedia.org/wiki/Lewis_and_Clark_Expedition",
        "source": "wikipedia:lewis_clark",
        "default_type": "trail",
    },
    {
        "url": "https://en.wikipedia.org/wiki/Lewis_and_Clark_National_Historic_Trail",
        "source": "wikipedia:lewis_clark_trail",
        "default_type": "trail",
    },
    # Natchez Trace & Old Spanish Trail
    {
        "url": "https://en.wikipedia.org/wiki/Natchez_Trace",
        "source": "wikipedia:natchez_trace",
        "default_type": "trail",
    },
    {
        "url": "https://en.wikipedia.org/wiki/Old_Spanish_Trail_(trade_route)",
        "source": "wikipedia:old_spanish_trail",
        "default_type": "trail",
    },
    # Trading posts / fur trade
    {
        "url": "https://en.wikipedia.org/wiki/List_of_trading_posts_of_the_American_fur_trade",
        "source": "wikipedia:trading_posts",
        "default_type": "trading_post",
    },
    # Native American battles
    {
        "url": "https://en.wikipedia.org/wiki/List_of_Indian_Wars_battles",
        "source": "wikipedia:indian_wars",
        "default_type": "battle",
    },
    # Other wars
    {
        "url": "https://en.wikipedia.org/wiki/List_of_battles_of_the_War_of_1812",
        "source": "wikipedia:war_of_1812",
        "default_type": "battle",
    },
    {
        "url": "https://en.wikipedia.org/wiki/List_of_battles_of_the_Mexican%E2%80%93American_War",
        "source": "wikipedia:mexican_american_war",
        "default_type": "battle",
    },
    {
        "url": "https://en.wikipedia.org/wiki/List_of_battles_of_the_Spanish%E2%80%93American_War",
        "source": "wikipedia:spanish_american_war",
        "default_type": "battle",
    },
    # Missions
    {
        "url": "https://en.wikipedia.org/wiki/List_of_California_missions",
        "source": "wikipedia:missions_california",
        "default_type": "mission",
    },
    {
        "url": "https://en.wikipedia.org/wiki/Spanish_missions_in_Texas",
        "source": "wikipedia:missions_texas",
        "default_type": "mission",
    },
    {
        "url": "https://en.wikipedia.org/wiki/Spanish_missions_in_New_Mexico",
        "source": "wikipedia:missions_new_mexico",
        "default_type": "mission",
    },
    {
        "url": "https://en.wikipedia.org/wiki/Spanish_missions_in_Arizona",
        "source": "wikipedia:missions_arizona",
        "default_type": "mission",
    },
    # Shipwrecks
    {
        "url": "https://en.wikipedia.org/wiki/List_of_shipwrecks_of_North_America",
        "source": "wikipedia:shipwrecks",
        "default_type": "shipwreck",
    },
    # Ferries
    {
        "url": "https://en.wikipedia.org/wiki/List_of_ferry_services_in_the_United_States",
        "source": "wikipedia:ferries",
        "default_type": "ferry",
    },
    # Ghost towns — additional states
    {
        "url": "https://en.wikipedia.org/wiki/List_of_ghost_towns_in_Alabama",
        "source": "wikipedia:ghost_towns_alabama",
        "default_type": "town",
    },
    {
        "url": "https://en.wikipedia.org/wiki/List_of_ghost_towns_in_Alaska",
        "source": "wikipedia:ghost_towns_alaska",
        "default_type": "town",
    },
    {
        "url": "https://en.wikipedia.org/wiki/List_of_ghost_towns_in_Arizona",
        "source": "wikipedia:ghost_towns_arizona",
        "default_type": "town",
    },
    {
        "url": "https://en.wikipedia.org/wiki/List_of_ghost_towns_in_Arkansas",
        "source": "wikipedia:ghost_towns_arkansas",
        "default_type": "town",
    },
    {
        "url": "https://en.wikipedia.org/wiki/List_of_ghost_towns_in_Idaho",
        "source": "wikipedia:ghost_towns_idaho",
        "default_type": "town",
    },
    {
        "url": "https://en.wikipedia.org/wiki/List_of_ghost_towns_in_Kansas",
        "source": "wikipedia:ghost_towns_kansas",
        "default_type": "town",
    },
    {
        "url": "https://en.wikipedia.org/wiki/List_of_ghost_towns_in_Montana",
        "source": "wikipedia:ghost_towns_montana",
        "default_type": "town",
    },
    {
        "url": "https://en.wikipedia.org/wiki/List_of_ghost_towns_in_Nevada",
        "source": "wikipedia:ghost_towns_nevada",
        "default_type": "town",
    },
    {
        "url": "https://en.wikipedia.org/wiki/List_of_ghost_towns_in_New_Mexico",
        "source": "wikipedia:ghost_towns_new_mexico",
        "default_type": "town",
    },
    {
        "url": "https://en.wikipedia.org/wiki/List_of_ghost_towns_in_Oregon",
        "source": "wikipedia:ghost_towns_oregon",
        "default_type": "town",
    },
    {
        "url": "https://en.wikipedia.org/wiki/List_of_ghost_towns_in_Texas",
        "source": "wikipedia:ghost_towns_texas",
        "default_type": "town",
    },
    {
        "url": "https://en.wikipedia.org/wiki/List_of_ghost_towns_in_Utah",
        "source": "wikipedia:ghost_towns_utah",
        "default_type": "town",
    },
    {
        "url": "https://en.wikipedia.org/wiki/List_of_ghost_towns_in_Washington_(state)",
        "source": "wikipedia:ghost_towns_washington",
        "default_type": "town",
    },
    {
        "url": "https://en.wikipedia.org/wiki/List_of_ghost_towns_in_Wyoming",
        "source": "wikipedia:ghost_towns_wyoming",
        "default_type": "town",
    },
    {
        "url": "https://en.wikipedia.org/wiki/List_of_ghost_towns_in_South_Dakota",
        "source": "wikipedia:ghost_towns_south_dakota",
        "default_type": "town",
    },
    {
        "url": "https://en.wikipedia.org/wiki/List_of_ghost_towns_in_North_Dakota",
        "source": "wikipedia:ghost_towns_north_dakota",
        "default_type": "town",
    },
    {
        "url": "https://en.wikipedia.org/wiki/List_of_ghost_towns_in_Nebraska",
        "source": "wikipedia:ghost_towns_nebraska",
        "default_type": "town",
    },
    {
        "url": "https://en.wikipedia.org/wiki/List_of_ghost_towns_in_Oklahoma",
        "source": "wikipedia:ghost_towns_oklahoma",
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
                    "wiki_title": name,
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
                        "wiki_title": name,
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
                    "wiki_title": name,
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


def _parse_generic_list_page(soup: BeautifulSoup, source: str) -> List[Dict[str, Any]]:
    """
    Generic parser for Wikipedia list pages.

    Tries wikitables first (extracts name from the first cell and description
    from the full row text).  Falls back to ``<ul><li>`` list parsing when
    no tables are found.  Coordinates are extracted from each row/li via
    ``_extract_coords_from_tag``.

    The ``default_type`` for each record is taken from the WIKIPEDIA_PAGES
    config entry.  It is resolved at call time via ``source``.
    """
    # Look up default_type from the page config
    default_type = "structure"
    for page_config in WIKIPEDIA_PAGES:
        if page_config["source"] == source:
            default_type = page_config.get("default_type", "structure")
            break

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

            description = row.get_text(separator=" ").strip()
            year = normalize_year(description)
            coords = _extract_coords_from_tag(row)

            records.append(
                {
                    "name": name,
                    "description": description[:500],
                    "year": year,
                    "latitude": coords[0] if coords else None,
                    "longitude": coords[1] if coords else None,
                    "source": source,
                    "location_hint": name,
                    "default_type": default_type,
                }
            )

    # Fallback: parse list items when no wikitable rows yielded results
    if not records:
        for li in soup.find_all("li"):
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
                    "location_hint": name,
                    "default_type": default_type,
                }
            )

    logger.info("Parsed %d generic list records from %s", len(records), source)
    return records


_PAGE_PARSERS = {
    "wikipedia:civil_war_battles": _parse_battles_page,
    "wikipedia:ghost_towns": _parse_ghost_towns_page,
    "wikipedia:historic_trails": _parse_trails_page,
    "wikipedia:revolutionary_war_battles": _parse_revolutionary_war_battles_page,
    "wikipedia:forts": _parse_forts_page,
    "wikipedia:ghost_towns_colorado": _parse_ghost_towns_page,
    "wikipedia:ghost_towns_california": _parse_ghost_towns_page,
    # Additional ghost town pages
    "wikipedia:ghost_towns_alabama": _parse_ghost_towns_page,
    "wikipedia:ghost_towns_alaska": _parse_ghost_towns_page,
    "wikipedia:ghost_towns_arizona": _parse_ghost_towns_page,
    "wikipedia:ghost_towns_arkansas": _parse_ghost_towns_page,
    "wikipedia:ghost_towns_idaho": _parse_ghost_towns_page,
    "wikipedia:ghost_towns_kansas": _parse_ghost_towns_page,
    "wikipedia:ghost_towns_montana": _parse_ghost_towns_page,
    "wikipedia:ghost_towns_nevada": _parse_ghost_towns_page,
    "wikipedia:ghost_towns_new_mexico": _parse_ghost_towns_page,
    "wikipedia:ghost_towns_oregon": _parse_ghost_towns_page,
    "wikipedia:ghost_towns_texas": _parse_ghost_towns_page,
    "wikipedia:ghost_towns_utah": _parse_ghost_towns_page,
    "wikipedia:ghost_towns_washington": _parse_ghost_towns_page,
    "wikipedia:ghost_towns_wyoming": _parse_ghost_towns_page,
    "wikipedia:ghost_towns_south_dakota": _parse_ghost_towns_page,
    "wikipedia:ghost_towns_north_dakota": _parse_ghost_towns_page,
    "wikipedia:ghost_towns_nebraska": _parse_ghost_towns_page,
    "wikipedia:ghost_towns_oklahoma": _parse_ghost_towns_page,
    # Battle pages
    "wikipedia:indian_wars": _parse_battles_page,
    "wikipedia:war_of_1812": _parse_battles_page,
    "wikipedia:mexican_american_war": _parse_battles_page,
    "wikipedia:spanish_american_war": _parse_battles_page,
    # Generic list pages (trading posts, missions, shipwrecks, ferries,
    # stagecoach routes, pony express)
    "wikipedia:trading_posts": _parse_generic_list_page,
    "wikipedia:missions_california": _parse_generic_list_page,
    "wikipedia:missions_texas": _parse_generic_list_page,
    "wikipedia:missions_new_mexico": _parse_generic_list_page,
    "wikipedia:missions_arizona": _parse_generic_list_page,
    "wikipedia:shipwrecks": _parse_generic_list_page,
    "wikipedia:ferries": _parse_generic_list_page,
    "wikipedia:stagecoach_butterfield": _parse_generic_list_page,
    "wikipedia:stagecoach_overland": _parse_generic_list_page,
    "wikipedia:stagecoach_central": _parse_generic_list_page,
    "wikipedia:pony_express": _parse_generic_list_page,
    # Wagon trail pages
    "wikipedia:oregon_trail": _parse_trails_page,
    "wikipedia:california_trail": _parse_trails_page,
    "wikipedia:mormon_trail": _parse_trails_page,
    "wikipedia:santa_fe_trail": _parse_trails_page,
    "wikipedia:el_camino_real": _parse_trails_page,
    "wikipedia:lewis_clark": _parse_trails_page,
    "wikipedia:lewis_clark_trail": _parse_trails_page,
    "wikipedia:natchez_trace": _parse_trails_page,
    "wikipedia:old_spanish_trail": _parse_trails_page,
}


# ---------------------------------------------------------------------------
# Geocoding enrichment
# ---------------------------------------------------------------------------

async def _enrich_with_geocoding(
    records: List[Dict[str, Any]],
    concurrency: int = 15,
) -> List[Dict[str, Any]]:
    """
    Fill in missing coordinates using Wikipedia Geosearch API with Nominatim fallback.

    Higher concurrency (15 vs the old 3) is safe because the Wikipedia API
    has no meaningful rate limit. Nominatim (1 req/sec) is only used as a
    last resort, and its rate limiting is enforced inside geocoding.geocode().

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
            # Try exact article title first (fastest path)
            wiki_title = record.get("wiki_title")
            if wiki_title:
                coords = await wiki_geocoding.get_article_coords(wiki_title)
                if coords:
                    record["latitude"], record["longitude"] = coords
                    return record

            # Fall back to geocode with location_hint (does wiki search then Nominatim)
            hint = record.get("location_hint", record["name"])
            coords = await geocoding.geocode(hint)
            if coords:
                record["latitude"], record["longitude"] = coords
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
        if is_blocked(rec["name"], rec.get("description", "")):
            logger.debug("Blocked record: %r", rec["name"])
            continue

        event_type = classify_event_type(rec["name"], rec.get("description", ""))
        default_type = rec.get("default_type", "event")

        # Only let the classifier override if the default_type is generic.
        # For specific scraper-assigned types (town, trail, stagecoach_stop,
        # ferry, mission, etc.) trust the scraper — it knows better.
        GENERIC_DEFAULT_TYPES = {"event", "structure"}
        if default_type not in GENERIC_DEFAULT_TYPES:
            # Specific default — trust the scraper
            event_type = default_type
        elif event_type == "event":
            # Classifier found nothing — fall back to scraper default
            event_type = default_type
        # else: classifier found something on a generic default — use it

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
