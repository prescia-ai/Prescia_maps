"""
Event type normalisation, confidence scoring, year parsing, and name cleaning.

All functions are pure (no I/O) and therefore synchronous — they are
designed to be called from async contexts without needing
``asyncio.run_in_executor``.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Optional

# Match the ORM enum values without importing from database to keep this
# module dependency-free.
LOCATION_TYPES = {
    "battle", "camp", "railroad_stop", "trail",
    "town", "mine", "structure", "event",
    "church", "school", "cemetery", "fairground",
    "ferry", "stagecoach_stop", "spring", "locale",
}

# Keyword sets used to classify events
_BATTLE_KEYWORDS = frozenset(
    ["battle", "siege", "skirmish", "engagement", "combat", "assault", "raid",
     "fight", "action at", "affair at"]
)
_CAMP_KEYWORDS = frozenset(
    ["camp", "encampment", "bivouac", "cantonment", "outpost", "fort", "post"]
)
_RAILROAD_KEYWORDS = frozenset(
    ["railroad", "railway", "depot", "station", "rail road", "rail line",
     "terminus", "junction"]
)
_TRAIL_KEYWORDS = frozenset(
    ["trail", "trace", "path", "road", "route", "highway", "pike", "turnpike",
     "emigrant"]
)
_TOWN_KEYWORDS = frozenset(
    ["town", "city", "village", "settlement", "ghost town", "community",
     "colony", "borough", "township", "county seat"]
)
_MINE_KEYWORDS = frozenset(
    ["mine", "mining", "quarry", "lode", "shaft", "pit", "colliery",
     "placer", "gold", "silver", "copper"]
)
_STRUCTURE_KEYWORDS = frozenset(
    ["bridge", "fort", "fortification", "redoubt", "earthwork", "battery",
     "blockhouse", "mill", "plantation", "building", "ruins", "monument",
     "courthouse"]
)
_CHURCH_KEYWORDS = frozenset(
    ["church", "chapel", "mission", "parish", "congregation"]
)
_SCHOOL_KEYWORDS = frozenset(
    ["school", "academy", "university", "college", "seminary"]
)
_CEMETERY_KEYWORDS = frozenset(
    ["cemetery", "graveyard", "burial", "memorial"]
)
_FAIRGROUND_KEYWORDS = frozenset(
    ["fairground", "fair", "carnival", "exposition", "pavilion"]
)
_FERRY_KEYWORDS = frozenset(
    ["ferry", "crossing", "ford"]
)
_SPRING_KEYWORDS = frozenset(
    ["spring", "hot spring", "mineral spring"]
)

# Regex patterns for year extraction
_YEAR_PATTERNS = [
    re.compile(r"\b(1[0-9]{3}|20[0-2][0-9])\b"),          # 4-digit year
    re.compile(r"\b([0-9]{1,4})\s*(?:AD|CE)\b", re.I),      # year AD/CE
    re.compile(r"\b([0-9]{1,4})\s*(?:BC|BCE)\b", re.I),     # year BC/BCE (negative)
    re.compile(r"circa\s+([0-9]{3,4})", re.I),              # circa YYYY
    re.compile(r"c\.\s*([0-9]{3,4})", re.I),                # c. YYYY
]

_BCE_PATTERN = re.compile(r"\b([0-9]{1,4})\s*(?:BC|BCE)\b", re.I)

# Characters / patterns to strip from names
_CLEANUP_PATTERN = re.compile(r"\s+")
_CITATION_PATTERN = re.compile(r"\[\d+\]")
_PARENTHETICAL_PATTERN = re.compile(r"\([^)]{0,60}\)")


def classify_event_type(name: str, description: str = "") -> str:
    """
    Classify a historical event into a ``LocationType`` value.

    The classifier works by counting keyword hits across the combined
    name and description text, then returning the category with the most
    matches.  Falls back to ``"event"`` when nothing matches.

    Args:
        name:        Display name of the event or location.
        description: Free-text description (may be empty).

    Returns:
        One of the ``LocationType`` enum string values.
    """
    combined = f"{name} {description}".lower()

    scores: dict[str, int] = {
        "battle": sum(1 for kw in _BATTLE_KEYWORDS if kw in combined),
        "camp": sum(1 for kw in _CAMP_KEYWORDS if kw in combined),
        "railroad_stop": sum(1 for kw in _RAILROAD_KEYWORDS if kw in combined),
        "trail": sum(1 for kw in _TRAIL_KEYWORDS if kw in combined),
        "town": sum(1 for kw in _TOWN_KEYWORDS if kw in combined),
        "mine": sum(1 for kw in _MINE_KEYWORDS if kw in combined),
        "structure": sum(1 for kw in _STRUCTURE_KEYWORDS if kw in combined),
        "church": sum(1 for kw in _CHURCH_KEYWORDS if kw in combined),
        "school": sum(1 for kw in _SCHOOL_KEYWORDS if kw in combined),
        "cemetery": sum(1 for kw in _CEMETERY_KEYWORDS if kw in combined),
        "fairground": sum(1 for kw in _FAIRGROUND_KEYWORDS if kw in combined),
        "ferry": sum(1 for kw in _FERRY_KEYWORDS if kw in combined),
        "spring": sum(1 for kw in _SPRING_KEYWORDS if kw in combined),
    }

    best_type = max(scores, key=lambda k: scores[k])
    return best_type if scores[best_type] > 0 else "event"


def assign_confidence(
    source: str,
    has_coords: bool,
    has_year: bool,
) -> float:
    """
    Compute a confidence score (0–1) for an extracted historical record.

    Higher confidence is assigned to records that come from authoritative
    sources, already have geographic coordinates, and include a dated year.

    Args:
        source:     Source label (e.g. ``"wikipedia"``, ``"usgs"``).
        has_coords: Whether the record carries explicit lat/lon data.
        has_year:   Whether a year could be extracted.

    Returns:
        Float in [0.0, 1.0].
    """
    score = 0.2  # base

    # Source authority weight
    source_lower = source.lower() if source else ""
    if "usgs" in source_lower or "nps" in source_lower:
        score += 0.4
    elif "wikipedia" in source_lower or "wiki" in source_lower:
        score += 0.25
    elif source_lower:
        score += 0.15

    # Bonus for having explicit coordinates
    if has_coords:
        score += 0.25

    # Bonus for having a year
    if has_year:
        score += 0.15

    return round(min(score, 1.0), 3)


def normalize_year(text: str) -> Optional[int]:
    """
    Extract the first plausible year from an arbitrary text string.

    Handles 4-digit years, ``AD``/``CE`` suffixes, ``BC``/``BCE`` suffixes
    (returned as negative integers), and ``circa`` / ``c.`` prefixes.

    Args:
        text: Raw string that may contain a year.

    Returns:
        Integer year, or ``None`` if no year could be found.
    """
    if not text:
        return None

    text = text.strip()

    # Check for BC/BCE years first to negate them
    bce_match = _BCE_PATTERN.search(text)
    if bce_match:
        return -int(bce_match.group(1))

    for pattern in _YEAR_PATTERNS:
        match = pattern.search(text)
        if match:
            try:
                return int(match.group(1))
            except (ValueError, IndexError):
                continue

    return None


def clean_name(name: str) -> str:
    """
    Normalise a raw scraped name into a clean display string.

    Steps applied:
    1. Unicode normalisation (NFC).
    2. Strip Wikipedia-style citation markers ``[1]``.
    3. Remove short parentheticals (e.g. disambiguation hints).
    4. Collapse whitespace.
    5. Title-case if the name is entirely upper or lower case.

    Args:
        name: Raw name string from a scraper or data source.

    Returns:
        Cleaned name string.
    """
    if not name:
        return ""

    # Unicode normalise
    name = unicodedata.normalize("NFC", name)

    # Strip citation markers
    name = _CITATION_PATTERN.sub("", name)

    # Remove disambiguation parentheticals shorter than 60 chars
    name = _PARENTHETICAL_PATTERN.sub("", name)

    # Collapse whitespace
    name = _CLEANUP_PATTERN.sub(" ", name).strip()

    # Fix all-caps or all-lowercase
    if name and (name.isupper() or name.islower()):
        name = name.title()

    return name
