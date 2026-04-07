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
    "mission", "trading_post", "shipwreck", "pony_express",
}

# Regex for battle detection — requires specific military-context phrases to
# avoid false positives from generic words like "assault", "fight", "combat".
_BATTLE_RE = re.compile(
    "|".join([
        r"battle\s+of",
        r"battle\s+at",
        r"siege\s+of",
        r"skirmish\s+(?:at|of|near)",
        r"engagement\s+(?:at|of)",
        r"assault\s+on",
        r"raid\s+on",
        r"action\s+at",
        r"affair\s+at",
        r"civil\s+war\s+battle",
        r"military\s+engagement",
        r"armed\s+conflict",
    ]),
    re.IGNORECASE,
)

# Keyword sets used to classify events
_CAMP_KEYWORDS = frozenset([
    "camp", "encampment", "bivouac", "cantonment",
    "army camp", "military camp", "soldier camp",
    "winter camp", "base camp",
])
_RAILROAD_KEYWORDS = frozenset(
    ["railroad", "railway", "depot", "station", "rail road", "rail line",
     "terminus", "junction"]
)
_TRAIL_KEYWORDS = frozenset(
    ["trail", "trace", "highway", "pike", "turnpike", "emigrant"]
)
_TOWN_KEYWORDS = frozenset(
    ["town", "city", "village", "settlement", "ghost town", "community",
     "colony", "borough", "township", "county seat"]
)
_MINE_KEYWORDS = frozenset(
    ["mine", "mining", "quarry", "lode", "shaft", "pit", "colliery",
     "placer", "gold", "silver", "copper"]
)
_STRUCTURE_KEYWORDS = frozenset([
    "bridge", "fort", "fortification", "redoubt", "earthwork", "battery",
    "blockhouse", "mill", "plantation", "building", "ruins", "monument",
    "courthouse", "outpost", "presidio", "stockade",
])
_CHURCH_KEYWORDS = frozenset(
    ["church", "chapel", "parish", "congregation"]
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
_MISSION_KEYWORDS = frozenset(
    ["mission", "presidio", "misión"]
)
_TRADING_POST_KEYWORDS = frozenset(
    ["trading post", "fur trade", "trading company", "fur trading"]
)
_PONY_EXPRESS_KEYWORDS = frozenset(
    ["pony express"]
)
_SHIPWRECK_KEYWORDS = frozenset(
    ["shipwreck", "sunk", "steamboat", "wreck", "sunken"]
)
_STAGECOACH_KEYWORDS = frozenset(
    ["stagecoach", "relay station", "overland mail", "stage stop",
     "stage route", "butterfield", "stage line"]
)

# Priority-ordered list of (type_name, keyword_set) for Tier 3 classification.
# Checked in order — first type with at least one keyword match wins.
_TIER3_TYPE_ORDER: list[tuple[str, frozenset]] = [
    ("mission",         _MISSION_KEYWORDS),
    ("trading_post",    _TRADING_POST_KEYWORDS),
    ("pony_express",    _PONY_EXPRESS_KEYWORDS),
    ("stagecoach_stop", _STAGECOACH_KEYWORDS),
    ("ferry",           _FERRY_KEYWORDS),
    ("shipwreck",       _SHIPWRECK_KEYWORDS),
    ("cemetery",        _CEMETERY_KEYWORDS),
    ("mine",            _MINE_KEYWORDS),
    ("church",          _CHURCH_KEYWORDS),
    ("school",          _SCHOOL_KEYWORDS),
    ("fairground",      _FAIRGROUND_KEYWORDS),
    ("spring",          _SPRING_KEYWORDS),
    ("camp",            _CAMP_KEYWORDS),
    ("railroad_stop",   _RAILROAD_KEYWORDS),
    ("town",            _TOWN_KEYWORDS),
    ("trail",           _TRAIL_KEYWORDS),
    ("structure",       _STRUCTURE_KEYWORDS),
]

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

    The classifier uses three priority tiers to avoid generic single-word
    keywords overriding specific multi-word phrases:

    1. **Tier 1** — exact multi-word phrase matches (highest priority).
       Returns immediately on first match.
    2. **Tier 2** — battle regex (phrase-level match).
    3. **Tier 3** — specific single-keyword types checked in priority order.
       Returns the first type whose keyword count is > 0.

    Falls back to ``"event"`` when nothing matches.

    Args:
        name:        Display name of the event or location.
        description: Free-text description (may be empty).

    Returns:
        One of the ``LocationType`` enum string values.
    """
    combined = f"{name} {description}".lower()

    # ------------------------------------------------------------------
    # Tier 1: high-specificity multi-word phrase matches — checked first
    # so they cannot be beaten by coincidental single-word keyword hits.
    # ------------------------------------------------------------------
    if "trading post" in combined or "fur trade" in combined or "fur trading" in combined:
        return "trading_post"
    if "pony express" in combined:
        return "pony_express"
    if (
        "stagecoach" in combined
        or "relay station" in combined
        or "overland mail" in combined
        or "stage stop" in combined
        or "stage line" in combined
        or "butterfield" in combined
    ):
        return "stagecoach_stop"
    if "ghost town" in combined:
        return "town"
    if "hot spring" in combined or "mineral spring" in combined:
        return "spring"
    if (
        "army camp" in combined
        or "military camp" in combined
        or "winter camp" in combined
        or "bivouac" in combined
        or "cantonment" in combined
        or "encampment" in combined
    ):
        return "camp"
    if "rail road" in combined or "rail line" in combined:
        return "railroad_stop"

    # ------------------------------------------------------------------
    # Tier 2: battle regex — phrase-level match (not a simple substring)
    # ------------------------------------------------------------------
    if _BATTLE_RE.search(combined):
        return "battle"

    # ------------------------------------------------------------------
    # Tier 3: single-keyword types checked in priority order.
    # First type with at least one keyword hit wins.
    # ------------------------------------------------------------------
    for type_name, keywords in _TIER3_TYPE_ORDER:
        if any(kw in combined for kw in keywords):
            return type_name

    # ------------------------------------------------------------------
    # Fallback
    # ------------------------------------------------------------------
    return "event"


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


# ---------------------------------------------------------------------------
# Metal-detecting blocklist — locations to exclude from the database
# ---------------------------------------------------------------------------

# These keywords indicate protected, inaccessible, or low-value locations.
# Records matching any of these are silently dropped during ingestion.
BLOCKLIST_PHRASES: frozenset[str] = frozenset([
    # Protected federal land — metal detecting prohibited
    "national park",
    "national monument",       # general monuments (not battlefield monuments)
    "national recreation area",
    "national seashore",
    "national lakeshore",
    "national preserve",
    "national wilderness",
    "wilderness area",
    "wildlife refuge",
    "national wildlife",
    "nature reserve",
    "nature preserve",
    "national forest",         # detecting allowed with permit but low coin density
    # State protected land
    "state park",
    "state forest",
    "state wildlife",
    "state nature",
    # Modern infrastructure — no historical artifacts
    "visitor center",
    "interpretive center",
    "museum",
    "gift shop",
    "parking lot",
    "campground",              # modern campground, not historic camp
    # Low-value modern locations
    "interstate highway",
    "shopping center",
    "airport",
    "military base",           # active military base
    "restricted area",
    "private property",
    # Broad categories with no coin loss value
    "national historic trail",  # the trail itself (linear), not a stop on it
])

# Exception keywords — if ANY of these appear alongside a blocklist phrase,
# the record is NOT blocked. e.g. "National Monument" alone is blocked, but
# "Battlefield National Monument" is NOT blocked.
BLOCKLIST_EXCEPTIONS: frozenset[str] = frozenset([
    "battlefield",
    "battle",
    "fort",
    "camp",
    "historic site",
    "historical site",
    "historic district",
    "trading post",
    "stage",
    "mission",
    "ferry",
    "mine",
    "ghost town",
    "cemetery",
])


def is_blocked(name: str, description: str = "") -> bool:
    """
    Return True if a record should be excluded from the database.

    A record is blocked if its name or description contains a blocklist
    phrase AND does not contain any exception keyword. This filters out
    national parks, protected areas, and modern infrastructure while
    preserving battlefield monuments, historic forts within parks, etc.

    Args:
        name:        Location name.
        description: Optional description text.

    Returns:
        True if the record should be dropped, False if it should be kept.
    """
    combined = f"{name} {description}".lower()

    # Check if any blocklist phrase matches
    matched_phrase = None
    for phrase in BLOCKLIST_PHRASES:
        if phrase in combined:
            matched_phrase = phrase
            break

    if matched_phrase is None:
        return False  # No blocklist match — keep the record

    # Check if any exception keyword saves it
    for exception in BLOCKLIST_EXCEPTIONS:
        if exception in combined:
            return False  # Exception found — keep the record

    return True  # Blocked


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
