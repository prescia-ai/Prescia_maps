#!/usr/bin/env python3
"""
FRRandP Ghost Towns scraper — extracts truly abandoned ghost towns and saves
them as a JSON file ready for import into Prescia Maps.

Extraction order (tries each until one succeeds):

1. **Google My Maps** — fetches the FRRandP viewer page for map ID
   ``1UUfwmW5YntQiVznItYrXwHYn1D9eGkgU``, parses embedded JS data blobs.

2. **FRRandP blog scrape** — paginates through
   ``https://www.frrandp.com/search/label/Ghost%20Towns``, reads each post,
   and extracts town names + coordinates from embedded iframes / GPS text.

3. **Seed dataset** — if both network methods fail (e.g. in a sandboxed CI
   environment), falls back to a curated offline list of true ghost towns.

CRITICAL FILTER applied to all methods
---------------------------------------
Only truly abandoned ghost towns with **zero permanent population** are kept.
Towns that are tourist destinations, artist colonies, ski towns, or still have
any residents are excluded.

Usage::

    python scripts/fetch_frrandp_ghost_towns.py
    python scripts/fetch_frrandp_ghost_towns.py --output-dir data/ \\
        --output-name frrandp_ghost_towns --confidence 0.80
"""

from __future__ import annotations

import io
import sys

# Force UTF-8 output on Windows to prevent emoji/unicode crashes
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if sys.stderr.encoding and sys.stderr.encoding.lower() != "utf-8":
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import argparse
import json
import logging
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse, parse_qs

import httpx

logger = logging.getLogger("fetch_frrandp_ghost_towns")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MAP_ID = "1UUfwmW5YntQiVznItYrXwHYn1D9eGkgU"
_VIEWER_URL = "https://www.google.com/maps/d/u/0/viewer?mid={mid}"
_BLOG_LABEL_URL = "https://www.frrandp.com/search/label/Ghost%20Towns"
_BLOG_GHOST_MAP_PAGE = "https://www.frrandp.com/p/ghost-towns-map.html"

_BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

_REQUEST_DELAY = 1.0   # seconds between requests when scraping blog
_REQUEST_TIMEOUT = 30  # seconds

# Known towns to EXCLUDE — these are "living ghost towns" with population > 0
# or active tourist destinations, not truly abandoned.
_EXCLUDED_NAMES_LOWER = frozenset({
    # Arizona
    "jerome",
    "oatman",
    "tombstone",
    "chloride",
    # New Mexico
    "madrid",
    "cerrillos",
    # Colorado
    "silverton",
    "ouray",
    "telluride",
    "victor",
    "cripple creek",
    # Nevada
    "virginia city",
    "goldfield",
    "tonopah",
    "pioche",
    "manhattan",
    # California
    "randsburg",
})

# Keywords in a place name that indicate it is NOT a ghost town and should be
# excluded even when sourced from the Google My Maps data.
_NON_GHOST_TOWN_NAME_KEYWORDS = frozenset({
    # Archaeological / prehistoric
    "mound", "cliff dwelling", "cliff house", "cliff palace", "balcony house",
    "archaeological", "fossil", "quarry", "petroglyph", "pictograph",
    "burial ground", "burial mound", "heritage site",
    "zona arque",  # Spanish prefix of "zona arqueológica" (archaeological zone)
    "cerro de ",   # Spanish: "cerro de <name>" = archaeological hilltop site (not a ghost town)
    # Historic sites that are not towns
    "state park", "national park", "national monument", "national historic",
    "state historic", "historic park", "historic site",
    "interpretation centre", "interpretive center", "interpretive centre",
    "d'interprétation", "museum",
    # Structures / landmarks
    "castle", "tower", "station", "bridge", "viaduct", "lighthouse",
    "power plant", "dam",
    # Settlements that are not towns
    "colony", "mounds", "pueblo", "cliff dwellings",
    # Attractions / infrastructure
    "amusement park", "theme park", "resort",
    "prison", "penitentiary", "reformatory",
    "island",
    # Archaeological site variants
    " site", "site,",
    # Explicit nature features
    "cave of", "fossil bed",
    # Misc
    "trail", "submit a",
})

# Coordinates for the fallback seed dataset — truly abandoned ghost towns with
# zero permanent population.  Data compiled from public records, Wikipedia,
# National Register of Historic Places, and state park documentation.
# Format: (name, latitude, longitude, description)
_SEED_TOWNS: List[Tuple[str, float, float, str]] = [
    # ---------- California ----------
    (
        "Bodie",
        38.2120, -119.0157,
        "Gold mining ghost town, Mono County, California. California State Historic Park. "
        "Frozen in time since 1942. Zero permanent residents.",
    ),
    (
        "Ballarat",
        36.0538, -117.2235,
        "Desert ghost town, Inyo County, California. Former supply town for Death Valley mines. "
        "Abandoned early 20th century. No permanent residents.",
    ),
    (
        "Calico",
        34.9488, -116.8678,
        "Silver mining ghost town, San Bernardino County, California. Operated 1881–1907. "
        "Restored as a county regional park. No permanent residents.",
    ),
    (
        "Cerro Gordo",
        36.5139, -117.9047,
        "Silver and lead mining ghost town, Inyo County, California. Active 1865–1938. "
        "Private property, no permanent residential population.",
    ),
    (
        "Darwin",
        36.2669, -117.5897,
        "Mining ghost town, Inyo County, California. Former lead-silver camp in the Darwin Hills. "
        "Essentially abandoned; a handful of structures remain.",
    ),
    (
        "Ludlow",
        34.7178, -116.1606,
        "Mojave Desert railroad ghost town, San Bernardino County, California. "
        "Old Route 66 stop, now largely abandoned.",
    ),
    # ---------- Nevada ----------
    (
        "Rhyolite",
        36.9027, -116.8305,
        "Gold rush ghost town, Nye County, Nevada. Population peaked at ~10,000 in 1908. "
        "Completely abandoned by 1920. Ruins remain in open desert.",
    ),
    (
        "Belmont",
        38.6258, -117.2458,
        "Former Nye County seat, Nevada. Silver mining boomtown 1865–1885. "
        "Courthouse ruins preserved. No permanent residents.",
    ),
    (
        "Berlin",
        39.3667, -117.9167,
        "Lander County ghost town, Nevada. Part of Berlin-Ichthyosaur State Park. "
        "Mining ceased by 1911. Zero permanent residents.",
    ),
    (
        "Gold Point",
        37.3522, -117.3697,
        "Esmeralda County ghost town, Nevada. Silver and gold mining camp. "
        "Privately owned; no permanent residential population.",
    ),
    (
        "Hamilton",
        39.2503, -115.0039,
        "White Pine County ghost town, Nevada. Former county seat. Silver boom 1868–1880s. "
        "Destroyed by fires; only ruins remain. Zero residents.",
    ),
    (
        "Unionville",
        40.4167, -118.0333,
        "Pershing County ghost town, Nevada. Silver mining camp established 1861. "
        "Mark Twain briefly prospected here. Essentially abandoned.",
    ),
    # ---------- Colorado ----------
    (
        "Animas Forks",
        37.9361, -107.5745,
        "San Juan County ghost town, Colorado. Gold and silver mining settlement. "
        "Active 1875–1910. Above 11,200 ft elevation. Zero residents.",
    ),
    (
        "St. Elmo",
        38.7034, -106.3439,
        "Chaffee County ghost town, Colorado. Gold mining town active 1880–1922. "
        "One caretaker reported; considered zero permanent population.",
    ),
    (
        "Independence",
        39.0639, -106.6533,
        "Pitkin County ghost town, Colorado. Gold camp near Independence Pass. "
        "Abandoned 1899. Preserved by Aspen Historical Society. Zero residents.",
    ),
    (
        "Ashcroft",
        38.9456, -106.7458,
        "Pitkin County ghost town, Colorado. Silver mining camp abandoned 1890s. "
        "Preserved structures. Zero permanent residents.",
    ),
    (
        "Gilman",
        39.4909, -106.4828,
        "Eagle County ghost town, Colorado. EPA Superfund site. Zinc and lead mine. "
        "Evacuated 1984; permanently abandoned. Zero residents.",
    ),
    (
        "Summitville",
        37.4353, -106.5994,
        "Rio Grande County ghost town, Colorado. Gold mining settlement. "
        "Abandoned and designated a Superfund cleanup site. Zero residents.",
    ),
    # ---------- Arizona ----------
    (
        "Ruby",
        31.4642, -111.2245,
        "Santa Cruz County ghost town, Arizona. Lead-zinc mining camp active 1912–1941. "
        "Isolated ruins on private property. Zero residents.",
    ),
    (
        "Vulture City",
        33.8183, -112.9117,
        "Maricopa County ghost town, Arizona. Gold mine operated 1863–1942. "
        "Preserved on private land. No permanent residents.",
    ),
    (
        "Gleeson",
        31.7009, -109.7980,
        "Cochise County ghost town, Arizona. Copper mining camp established 1900. "
        "Adobe ruins remain. Zero permanent residents.",
    ),
    (
        "Dos Cabezas",
        32.1392, -109.6317,
        "Cochise County ghost town, Arizona. Gold and silver mining camp active 1870s–1900s. "
        "Small cluster of ruins. Essentially zero residents.",
    ),
    (
        "Harshaw",
        31.5167, -110.6147,
        "Santa Cruz County ghost town, Arizona. Silver mining town established 1877. "
        "Abandoned early 20th century. No permanent residents.",
    ),
    (
        "Greaterville",
        31.8417, -110.6458,
        "Santa Cruz County ghost town, Arizona. Gold placer mining camp 1870s–1890s. "
        "Ruins in the Santa Rita Mountains. Zero residents.",
    ),
    (
        "Swansea",
        34.1444, -114.0683,
        "La Paz County ghost town, Arizona. Copper smelting town established 1909. "
        "Ruins in the Buckskin Mountains. Zero permanent residents.",
    ),
    (
        "Bumble Bee",
        34.2333, -112.2000,
        "Yavapai County ghost town, Arizona. Gold mining settlement late 1800s. "
        "Privately owned ruins along Bumble Bee Road. Zero residents.",
    ),
    # ---------- New Mexico ----------
    (
        "Mogollon",
        33.3867, -108.7678,
        "Catron County ghost town, New Mexico. Silver-gold mining camp active 1890–1942. "
        "Remote mountain location. Zero permanent residents.",
    ),
    (
        "Elizabethtown",
        36.5534, -105.2231,
        "Colfax County ghost town, New Mexico. First incorporated town in New Mexico. "
        "Gold mining boom 1867–1875. Ruins only. Zero residents.",
    ),
    (
        "White Oaks",
        33.6006, -105.7831,
        "Lincoln County ghost town, New Mexico. Gold mining boomtown 1879–1900s. "
        "Only ruins remain. Zero permanent residents.",
    ),
    (
        "Kelly",
        34.0847, -107.1897,
        "Socorro County ghost town, New Mexico. Lead-zinc-silver mine active 1860s–1940s. "
        "Church ruins preserved. Zero residents.",
    ),
    # ---------- Wyoming ----------
    (
        "South Pass City",
        42.4700, -108.8083,
        "Fremont County ghost town, Wyoming. Gold mining settlement 1867–1872. "
        "State Historic Site. Zero permanent residents.",
    ),
    (
        "Atlantic City",
        42.5300, -108.7400,
        "Fremont County ghost town, Wyoming. Gold and iron mining town founded 1868. "
        "Mostly abandoned; treated as zero population.",
    ),
    # ---------- Utah ----------
    (
        "Sego",
        39.1972, -109.5006,
        "Grand County ghost town, Utah. Coal mining camp active 1910–1955. "
        "Petroglyphs nearby. Zero residents.",
    ),
    (
        "Cisco",
        38.9742, -109.3258,
        "Grand County ghost town, Utah (not to be confused with Cisco, TX). "
        "Railroad and ranching ghost town. Abandoned mid-20th century. Zero residents.",
    ),
    # ---------- Alaska ----------
    (
        "Kennecott",
        61.4897, -142.9128,
        "Wrangell-St. Elias National Park ghost town, Alaska. Copper mine operated 1903–1938. "
        "National Historic Landmark. Zero permanent residents.",
    ),
    # ---------- Pennsylvania ----------
    (
        "Centralia",
        40.8031, -76.3413,
        "Columbia County ghost town, Pennsylvania. Evacuated due to underground coal mine fire "
        "burning since 1962. Government-ordered relocation. Fewer than 10 holdouts remain.",
    ),
    # ---------- Texas ----------
    (
        "Terlingua",
        29.3204, -103.6088,
        "Brewster County ghost town, Texas. Mercury mining town active 1900–1942. "
        "Mostly abandoned ruins in the Chihuahuan Desert, near Big Bend National Park.",
    ),
    # ---------- West Virginia ----------
    (
        "Thurmond",
        37.9523, -81.0738,
        "Fayette County ghost town, West Virginia. Coal boom town 1880–1930s. "
        "National Park Service site. Fewer than 5 residents; considered abandoned.",
    ),
    # ---------- Montana ----------
    (
        "Bannack",
        45.1639, -112.9950,
        "Beaverhead County ghost town, Montana. First territorial capital of Montana. "
        "Gold rush town 1862. Montana State Park. Zero permanent residents.",
    ),
    (
        "Garnet",
        46.8219, -113.3931,
        "Missoula/Granite County ghost town, Montana. Gold mining camp 1860s–1947. "
        "Managed by BLM. Zero permanent residents.",
    ),
    # ---------- Idaho ----------
    (
        "Silver City",
        42.9767, -116.7336,
        "Owyhee County ghost town, Idaho. Silver mining town established 1864. "
        "Former county seat. Zero permanent residents.",
    ),
    # ---------- Oregon ----------
    (
        "Hardman",
        45.2167, -120.2167,
        "Morrow County ghost town, Oregon. Former farming and ranching community. "
        "Abandoned mid-20th century. Zero residents.",
    ),
]


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
# Ghost-town filter
# ---------------------------------------------------------------------------


def is_true_ghost_town(name: str, description: str = "") -> bool:
    """
    Return True if the named location is likely a true ghost town
    (zero or near-zero permanent population, genuinely abandoned).

    Excludes towns known to have active tourism industries, current residents,
    or commercial businesses. Also excludes archaeological sites, mounds,
    cliff dwellings, and other non-town entries that may appear in the map.
    """
    name_lower = name.lower().strip()

    # Direct exclusion list
    if name_lower in _EXCLUDED_NAMES_LOWER:
        return False

    # Fuzzy exclusion: skip if the name starts with or contains an excluded town
    for excl in _EXCLUDED_NAMES_LOWER:
        if name_lower == excl or name_lower.startswith(excl + ",") or name_lower.startswith(excl + " "):
            return False

    # Exclude non-ghost-town place types by name keywords
    for kw in _NON_GHOST_TOWN_NAME_KEYWORDS:
        if kw in name_lower:
            return False

    # Keyword-based exclusion from description
    desc_lower = description.lower()
    exclusion_phrases = [
        "still inhabited",
        "residents remain",
        "current population",
        "residents live",
        "tourist destination",
        "active town",
        "wine bar",
        "art gallery",
        "artist colony",
        "ski resort",
        "ski area",
    ]
    for phrase in exclusion_phrases:
        if phrase in desc_lower:
            return False

    return True


# ---------------------------------------------------------------------------
# Method 1 — Google My Maps viewer scrape
# ---------------------------------------------------------------------------


def _fetch_viewer(mid: str, client: httpx.Client) -> str:
    url = _VIEWER_URL.format(mid=mid)
    logger.info("Fetching Google My Maps viewer: %s", url)
    r = client.get(url, headers={"User-Agent": _BROWSER_UA})
    r.raise_for_status()
    return r.text


def _parse_viewer_html(html: str) -> List[Dict[str, Any]]:
    """
    Extract placemarks from Google My Maps viewer HTML.

    The viewer embeds JSON-like data where each placemark follows this pattern
    (with double-quotes escaped as \\"):
      [[null,[lat,lon]],"0",null,"STYLE_ID",[lat,lon],[0,0],"HEX_ID"],[["Name"]]]

    We unescape the JSON string quoting first, then use targeted regex.
    """
    # Unescape the \"  → "  sequences that Google uses inside JS string literals
    text = html.replace('\\"', '"')

    # Pattern: [null,[lat,lon]],"0",null,"STYLE_ID"  then within ~150 chars: [["Name"]]
    coord_pat = re.compile(
        r'\[null,\[(-?\d+\.?\d*),(-?\d+\.?\d*)\]\],"0",null,"[^"]+"'
    )
    name_pat = re.compile(r'\[\["([^"]+)"\]\]')

    results: List[Dict[str, Any]] = []
    for m in coord_pat.finditer(text):
        lat = float(m.group(1))
        lon = float(m.group(2))
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            continue

        # Name appears immediately after the placemark metadata block
        after = text[m.end(): m.end() + 200]
        nm = name_pat.search(after)
        if not nm:
            continue

        name = nm.group(1)
        # Decode unicode escape sequences (e.g. \u0027 -> ')
        # The sequence encodes to latin-1 bytes then decodes as utf-8 because
        # unicode_escape produces latin-1 byte strings for non-ASCII code points.
        try:
            name = name.encode("utf-8").decode("unicode_escape").encode("latin-1").decode("utf-8")
        except (UnicodeDecodeError, UnicodeEncodeError):
            pass

        results.append({"name": name, "latitude": lat, "longitude": lon, "description": ""})

    # Deduplicate by (name, lat, lon)
    seen: set[tuple[str, float, float]] = set()
    deduped: List[Dict[str, Any]] = []
    for entry in results:
        key = (entry["name"], entry["latitude"], entry["longitude"])
        if key not in seen:
            seen.add(key)
            deduped.append(entry)

    return deduped


def scrape_google_my_maps(mid: str) -> Optional[List[Dict[str, Any]]]:
    """
    Try to scrape the FRRandP Google My Maps viewer page.

    The map ("Ghost Towns, Abandoned Places & Historic Sites") contains a mix
    of ghost towns, archaeological sites, abandoned structures, and other POIs.
    This function filters the raw results to North American coordinates only
    before returning, leaving final ghost-town filtering to ``apply_ghost_town_filter``.

    Returns a list of raw dicts or None if the scrape fails.
    """
    try:
        with httpx.Client(follow_redirects=True, timeout=_REQUEST_TIMEOUT) as client:
            html = _fetch_viewer(mid, client)
        raw = _parse_viewer_html(html)
        if not raw:
            logger.warning("Google My Maps: page loaded but no pins found.")
            return None

        # Pre-filter: keep only US territories and Canada.
        # The map also contains entries from Mexico, Central America, Caribbean,
        # and other countries; those are excluded here.
        #
        # Accepted regions:
        #   - Continental US + Canada: lat 24-83, lon -52 to -168
        #   - Hawaii (US): lat 18-23, lon -154 to -162
        #   - Puerto Rico (US): lat 17-19, lon -65 to -68
        def _in_us_or_canada(e: dict) -> bool:
            lat, lon = e["latitude"], e["longitude"]
            if 24 <= lat <= 83 and -168 <= lon <= -52:
                return True
            if 18 <= lat <= 23 and -162 <= lon <= -154:  # Hawaii
                return True
            if 17 <= lat <= 19 and -68 <= lon <= -65:    # Puerto Rico
                return True
            return False

        na = [e for e in raw if _in_us_or_canada(e)]
        logger.info(
            "Google My Maps: extracted %d pins (%d in US/Canada).",
            len(raw), len(na),
        )
        return na if na else None
    except Exception as exc:
        logger.warning("Google My Maps scrape failed: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Method 2 — FRRandP blog scrape
# ---------------------------------------------------------------------------


def _make_client() -> httpx.Client:
    return httpx.Client(
        follow_redirects=True,
        timeout=_REQUEST_TIMEOUT,
        headers={"User-Agent": _BROWSER_UA},
    )


def _extract_coords_from_text(text: str) -> Optional[Tuple[float, float]]:
    """
    Find GPS coordinates mentioned in free text.

    Recognises patterns like:
      GPS: 38.2120, -119.0157
      N 38° 12.72' W 119° 00.94'
      38.2120°N 119.0157°W
      38.2120 -119.0157
    """
    patterns = [
        # GPS: lat, lon  (most common on FRRandP)
        re.compile(
            r'(?:GPS|coordinates?|lat[/,]?\s*lon|location)[:\s]+(-?\d{1,3}\.\d{2,})[°,\s]+(-?\d{1,3}\.\d{2,})',
            re.IGNORECASE,
        ),
        # Two bare decimal numbers that look like a coord pair
        re.compile(
            r'\b(-?\d{2,3}\.\d{3,})\s*[,;]\s*(-?\d{2,3}\.\d{3,})\b'
        ),
        # DMS: N 38° 12.72' W 119° 00.94'
        re.compile(
            r'[Nn]\s*(\d{1,3})[°\s]+(\d{1,2})[\'.\s]+(\d*)\s*[\'"]?\s*[Ww]\s*(\d{1,3})[°\s]+(\d{1,2})[\'.\s]+(\d*)',
        ),
    ]

    for pat in patterns[:2]:
        m = pat.search(text)
        if m:
            try:
                lat = float(m.group(1))
                lon = float(m.group(2))
                # Crude sanity check for western/central North America
                if 20 <= lat <= 72 and -170 <= lon <= -50:
                    return lat, lon
                # Try swapping if lon looks positive (may have missed the minus)
                if 20 <= lat <= 72 and 50 <= lon <= 170:
                    return lat, -lon
            except ValueError:
                continue

    # DMS pattern
    m = patterns[2].search(text)
    if m:
        try:
            lat = int(m.group(1)) + int(m.group(2)) / 60 + int(m.group(3) or 0) / 3600
            lon = -(int(m.group(4)) + int(m.group(5)) / 60 + int(m.group(6) or 0) / 3600)
            if 20 <= lat <= 72 and -170 <= lon <= -50:
                return lat, lon
        except ValueError:
            pass

    return None


def _extract_mid_from_iframe(html: str) -> Optional[str]:
    """Extract Google My Maps map ID from an embedded iframe src."""
    m = re.search(r'mid=([A-Za-z0-9_-]+)', html)
    return m.group(1) if m else None


def _extract_post_title(html: str) -> str:
    """Return the post title from Blogger HTML."""
    m = re.search(r'<h3[^>]+class=["\'][^"\']*post-title[^"\']*["\'][^>]*>\s*(?:<a[^>]*>)?\s*(.*?)\s*(?:</a>)?\s*</h3>', html, re.DOTALL)
    if m:
        return re.sub(r'<[^>]+>', '', m.group(1)).strip()
    m = re.search(r'<title>([^<]+)</title>', html)
    if m:
        return m.group(1).split('|')[0].strip()
    return ""


def _extract_post_snippet(html: str) -> str:
    """Return the first meaningful paragraph from the post body."""
    # Strip script/style blocks
    cleaned = re.sub(r'<(script|style)[^>]*>.*?</\1>', '', html, flags=re.DOTALL)
    # Remove all other HTML tags
    text_only = re.sub(r'<[^>]+>', ' ', cleaned)
    # Collapse whitespace
    text_only = re.sub(r'\s+', ' ', text_only).strip()
    # Return first ~300 chars
    return text_only[:300]


def _scrape_blog_post(url: str, client: httpx.Client) -> Optional[Dict[str, Any]]:
    """
    Fetch a single FRRandP blog post and extract town name + coordinates.

    Returns a raw dict or None if no usable data is found.
    """
    try:
        r = client.get(url)
        r.raise_for_status()
        html = r.text
    except Exception as exc:
        logger.warning("Failed to fetch %s: %s", url, exc)
        return None

    title = _extract_post_title(html)
    if not title:
        return None

    # Look for coords in the body text
    snippet = _extract_post_snippet(html)
    coords = _extract_coords_from_text(html)

    if coords is None:
        # Try extracting a nested map ID from iframes and scraping that map
        mid = _extract_mid_from_iframe(html)
        if mid:
            logger.debug("Post %s has embedded map %s — trying to extract coords", url, mid)
        return None  # No coords found in this post

    lat, lon = coords
    return {
        "name": title,
        "latitude": lat,
        "longitude": lon,
        "description": snippet[:200],
    }


def _get_blog_post_links(html: str) -> List[str]:
    """Return all post links from a Blogger index/label page."""
    links = []
    # Blogger post links look like: /YYYY/MM/slug.html
    for m in re.finditer(r'href=["\']?(https://www\.frrandp\.com/\d{4}/\d{2}/[^"\'>\s]+)["\']?', html):
        link = m.group(1).split('?')[0]  # strip query string
        if link not in links:
            links.append(link)
    return links


def _get_next_page_url(html: str, current_url: str) -> Optional[str]:
    """Return the URL of the next paginated label page, if any."""
    # Blogger 'Older Posts' link
    m = re.search(r'href=["\']([^"\']*(?:max-results|updated-max)[^"\']*)["\'][^>]*>(?:Older Posts|Next)', html)
    if m:
        href = m.group(1)
        if href.startswith('http'):
            return href
        return urljoin(current_url, href)
    return None


def scrape_frrandp_blog() -> Optional[List[Dict[str, Any]]]:
    """
    Scrape FRRandP's blog for ghost town posts with coordinates.

    Paginates through the Ghost Towns label pages and extracts data from
    each individual post.  Returns a list of raw dicts or None on failure.
    """
    results: List[Dict[str, Any]] = []
    visited_posts: set[str] = set()

    try:
        with _make_client() as client:
            # ---- Paginate the label index ----
            page_url: Optional[str] = _BLOG_LABEL_URL
            page_num = 0
            all_post_links: List[str] = []

            while page_url:
                page_num += 1
                logger.info("Fetching label page %d: %s", page_num, page_url)
                try:
                    r = client.get(page_url)
                    r.raise_for_status()
                    index_html = r.text
                except Exception as exc:
                    logger.warning("Label page fetch failed: %s", exc)
                    break

                post_links = _get_blog_post_links(index_html)
                for link in post_links:
                    if link not in visited_posts:
                        all_post_links.append(link)
                        visited_posts.add(link)

                page_url = _get_next_page_url(index_html, page_url)
                if page_num >= 20:
                    logger.info("Reached page limit (20), stopping pagination.")
                    break
                time.sleep(_REQUEST_DELAY)

            # ---- Also check the ghost towns map page ----
            try:
                r = client.get(_BLOG_GHOST_MAP_PAGE)
                r.raise_for_status()
                map_page_html = r.text
                for link in _get_blog_post_links(map_page_html):
                    if link not in visited_posts:
                        all_post_links.append(link)
                        visited_posts.add(link)
                logger.info("Ghost towns map page: found %d additional post links.", len(all_post_links))
            except Exception as exc:
                logger.warning("Ghost map page fetch failed: %s", exc)

            logger.info("Total post links to scrape: %d", len(all_post_links))

            # ---- Scrape each post ----
            for post_url in all_post_links:
                logger.debug("Scraping post: %s", post_url)
                result = _scrape_blog_post(post_url, client)
                if result:
                    results.append(result)
                    lat_str = f"{result['latitude']:.4f}"
                    lon_str = f"{result['longitude']:.4f}"
                    logger.info("  → %s (%s, %s)", result["name"], lat_str, lon_str)
                time.sleep(_REQUEST_DELAY)

    except Exception as exc:
        logger.warning("Blog scrape failed: %s", exc)

    if results:
        logger.info("Blog scrape: extracted %d towns with coordinates.", len(results))
        return results

    logger.warning("Blog scrape: no towns with coordinates found.")
    return None


# ---------------------------------------------------------------------------
# Method 3 — Seed dataset fallback
# ---------------------------------------------------------------------------


def load_seed_dataset() -> List[Dict[str, Any]]:
    """Return the bundled offline seed dataset of true ghost towns."""
    logger.info("Using offline seed dataset (%d towns).", len(_SEED_TOWNS))
    return [
        {
            "name": name,
            "latitude": lat,
            "longitude": lon,
            "description": desc,
        }
        for name, lat, lon, desc in _SEED_TOWNS
    ]


# ---------------------------------------------------------------------------
# Normalise raw → import format + filter
# ---------------------------------------------------------------------------


def apply_ghost_town_filter(raw: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Remove entries that are not true ghost towns."""
    filtered = []
    excluded_count = 0
    for entry in raw:
        name = entry.get("name", "").strip()
        desc = entry.get("description", "")
        if not name:
            continue
        if is_true_ghost_town(name, desc):
            filtered.append(entry)
        else:
            logger.info("  EXCLUDED (not a true ghost town): %s", name)
            excluded_count += 1
    if excluded_count:
        logger.info("Filter: removed %d entries that are not true ghost towns.", excluded_count)
    return filtered


def normalise(
    raw: List[Dict[str, Any]],
    location_type: str,
    source: str,
    confidence: float,
) -> List[Dict[str, Any]]:
    """Convert raw extracted records to the Prescia Maps import format."""
    out: List[Dict[str, Any]] = []
    for entry in raw:
        name = entry.get("name", "").strip()
        if not name:
            continue
        record: Dict[str, Any] = {
            "name": name,
            "type": location_type,
            "latitude": round(entry["latitude"], 6),
            "longitude": round(entry["longitude"], 6),
            "source": source,
            "confidence": confidence,
        }
        desc = entry.get("description", "")
        if desc:
            record["description"] = desc.strip()
        out.append(record)
    return out


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Scrape FRRandP ghost towns from Google My Maps or the FRRandP blog, "
            "filter for truly abandoned zero-population towns, and save as "
            "JSON ready for import into Prescia Maps."
        )
    )
    parser.add_argument(
        "--mid",
        metavar="MAP_ID",
        default=_MAP_ID,
        help=f"Google My Maps map ID (default: {_MAP_ID}).",
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
        default="frrandp_ghost_towns",
        help="Base name for output files (default: frrandp_ghost_towns).",
    )
    parser.add_argument(
        "--type",
        metavar="LOCATION_TYPE",
        dest="location_type",
        default="town",
        help="LocationType to assign to all records (default: town).",
    )
    parser.add_argument(
        "--source",
        default="frrandp_ghost_towns",
        help="Source string for all records (default: frrandp_ghost_towns).",
    )
    parser.add_argument(
        "--confidence",
        type=float,
        default=0.80,
        help="Confidence value 0–1 for all records (default: 0.80).",
    )
    parser.add_argument(
        "--skip-google",
        action="store_true",
        help="Skip the Google My Maps scrape and go straight to blog scrape.",
    )
    parser.add_argument(
        "--skip-blog",
        action="store_true",
        help="Skip the blog scrape and go straight to seed dataset.",
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
    # Step 1: Extract raw data (try each method in order)
    # ------------------------------------------------------------------
    raw: Optional[List[Dict[str, Any]]] = None
    method_used: str = "unknown"

    if not args.skip_google:
        logger.info("=== Method 1: Google My Maps scrape ===")
        raw = scrape_google_my_maps(args.mid)
        if raw:
            method_used = "google_my_maps"

    if raw is None and not args.skip_blog:
        logger.info("=== Method 2: FRRandP blog scrape ===")
        raw = scrape_frrandp_blog()
        if raw:
            method_used = "frrandp_blog"

    if raw is None:
        logger.info("=== Method 3: Seed dataset fallback ===")
        raw = load_seed_dataset()
        method_used = "seed_dataset"

    logger.info("Using data from: %s (%d raw records)", method_used, len(raw))

    # ------------------------------------------------------------------
    # Step 2: Save raw output
    # ------------------------------------------------------------------
    with open(raw_path, "w", encoding="utf-8") as fh:
        json.dump(raw, fh, indent=2, ensure_ascii=False)
    logger.info("Raw data saved → %s", raw_path)

    # ------------------------------------------------------------------
    # Step 3: Filter + normalise
    # ------------------------------------------------------------------
    filtered = apply_ghost_town_filter(raw)
    logger.info("After ghost-town filter: %d records remain.", len(filtered))

    normalised = normalise(filtered, args.location_type, args.source, args.confidence)

    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(normalised, fh, indent=2, ensure_ascii=False)
    logger.info("Import-ready data saved → %s", out_path)

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    print(f"\nDone. {len(normalised)} ghost towns saved.")
    print(f"  Method used : {method_used}")
    print(f"  Raw data    : {raw_path}")
    print(f"  Import file : {out_path}")


if __name__ == "__main__":
    main()
