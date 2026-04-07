"""
Second async Wikipedia scraper — covers URLs not included in ``wikipedia.py``.

Extends the first scraper with:
- Ghost towns for all remaining US states
- Old / defunct railroads
- Additional stagecoach routes
- Historic settlements and unincorporated communities
- Gold-rush sites and old mines
- Additional wagon / emigrant trails
- Additional frontier-era battles
- Ferries and river crossings
- Old cemeteries
- Additional Spanish missions
- Shipwrecks (Great Lakes and coasts)

All parser functions, coordinate helpers, geocoding enrichment, and the
``scrape_source`` pattern are reused from :mod:`app.scrapers.wikipedia`.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List

import httpx
from bs4 import BeautifulSoup

from app.scrapers.normalizer import assign_confidence, classify_event_type, is_blocked
from app.scrapers.wikipedia import (
    _GENERIC_DEFAULT_TYPES,
    _enrich_with_geocoding,
    _fetch_page,
    _parse_battles_page,
    _parse_ghost_towns_page,
    _parse_trails_page,
    _parse_generic_list_page as _parse_generic_list_page_orig,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Target pages — only URLs NOT already present in WIKIPEDIA_PAGES
# ---------------------------------------------------------------------------

WIKIPEDIA_PAGES_2: List[Dict[str, str]] = [
    # ------------------------------------------------------------------
    # Ghost towns — remaining states (not covered in the first script)
    # ------------------------------------------------------------------
    {
        "url": "https://en.wikipedia.org/wiki/List_of_ghost_towns_in_Connecticut",
        "source": "wikipedia:ghost_towns_connecticut",
        "default_type": "town",
    },
    {
        "url": "https://en.wikipedia.org/wiki/List_of_ghost_towns_in_Delaware",
        "source": "wikipedia:ghost_towns_delaware",
        "default_type": "town",
    },
    {
        "url": "https://en.wikipedia.org/wiki/List_of_ghost_towns_in_Florida",
        "source": "wikipedia:ghost_towns_florida",
        "default_type": "town",
    },
    {
        "url": "https://en.wikipedia.org/wiki/List_of_ghost_towns_in_Georgia_(U.S._state)",
        "source": "wikipedia:ghost_towns_georgia",
        "default_type": "town",
    },
    {
        "url": "https://en.wikipedia.org/wiki/List_of_ghost_towns_in_Hawaii",
        "source": "wikipedia:ghost_towns_hawaii",
        "default_type": "town",
    },
    {
        "url": "https://en.wikipedia.org/wiki/List_of_ghost_towns_in_Illinois",
        "source": "wikipedia:ghost_towns_illinois",
        "default_type": "town",
    },
    {
        "url": "https://en.wikipedia.org/wiki/List_of_ghost_towns_in_Indiana",
        "source": "wikipedia:ghost_towns_indiana",
        "default_type": "town",
    },
    {
        "url": "https://en.wikipedia.org/wiki/List_of_ghost_towns_in_Iowa",
        "source": "wikipedia:ghost_towns_iowa",
        "default_type": "town",
    },
    {
        "url": "https://en.wikipedia.org/wiki/List_of_ghost_towns_in_Kentucky",
        "source": "wikipedia:ghost_towns_kentucky",
        "default_type": "town",
    },
    {
        "url": "https://en.wikipedia.org/wiki/List_of_ghost_towns_in_Louisiana",
        "source": "wikipedia:ghost_towns_louisiana",
        "default_type": "town",
    },
    {
        "url": "https://en.wikipedia.org/wiki/List_of_ghost_towns_in_Maine",
        "source": "wikipedia:ghost_towns_maine",
        "default_type": "town",
    },
    {
        "url": "https://en.wikipedia.org/wiki/List_of_ghost_towns_in_Maryland",
        "source": "wikipedia:ghost_towns_maryland",
        "default_type": "town",
    },
    {
        "url": "https://en.wikipedia.org/wiki/List_of_ghost_towns_in_Massachusetts",
        "source": "wikipedia:ghost_towns_massachusetts",
        "default_type": "town",
    },
    {
        "url": "https://en.wikipedia.org/wiki/List_of_ghost_towns_in_Michigan",
        "source": "wikipedia:ghost_towns_michigan",
        "default_type": "town",
    },
    {
        "url": "https://en.wikipedia.org/wiki/List_of_ghost_towns_in_Minnesota",
        "source": "wikipedia:ghost_towns_minnesota",
        "default_type": "town",
    },
    {
        "url": "https://en.wikipedia.org/wiki/List_of_ghost_towns_in_Mississippi",
        "source": "wikipedia:ghost_towns_mississippi",
        "default_type": "town",
    },
    {
        "url": "https://en.wikipedia.org/wiki/List_of_ghost_towns_in_Missouri",
        "source": "wikipedia:ghost_towns_missouri",
        "default_type": "town",
    },
    {
        "url": "https://en.wikipedia.org/wiki/List_of_ghost_towns_in_New_Hampshire",
        "source": "wikipedia:ghost_towns_new_hampshire",
        "default_type": "town",
    },
    {
        "url": "https://en.wikipedia.org/wiki/List_of_ghost_towns_in_New_Jersey",
        "source": "wikipedia:ghost_towns_new_jersey",
        "default_type": "town",
    },
    {
        "url": "https://en.wikipedia.org/wiki/List_of_ghost_towns_in_New_York",
        "source": "wikipedia:ghost_towns_new_york",
        "default_type": "town",
    },
    {
        "url": "https://en.wikipedia.org/wiki/List_of_ghost_towns_in_North_Carolina",
        "source": "wikipedia:ghost_towns_north_carolina",
        "default_type": "town",
    },
    {
        "url": "https://en.wikipedia.org/wiki/List_of_ghost_towns_in_Ohio",
        "source": "wikipedia:ghost_towns_ohio",
        "default_type": "town",
    },
    {
        "url": "https://en.wikipedia.org/wiki/List_of_ghost_towns_in_Pennsylvania",
        "source": "wikipedia:ghost_towns_pennsylvania",
        "default_type": "town",
    },
    {
        "url": "https://en.wikipedia.org/wiki/List_of_ghost_towns_in_Rhode_Island",
        "source": "wikipedia:ghost_towns_rhode_island",
        "default_type": "town",
    },
    {
        "url": "https://en.wikipedia.org/wiki/List_of_ghost_towns_in_South_Carolina",
        "source": "wikipedia:ghost_towns_south_carolina",
        "default_type": "town",
    },
    {
        "url": "https://en.wikipedia.org/wiki/List_of_ghost_towns_in_Tennessee",
        "source": "wikipedia:ghost_towns_tennessee",
        "default_type": "town",
    },
    {
        "url": "https://en.wikipedia.org/wiki/List_of_ghost_towns_in_Vermont",
        "source": "wikipedia:ghost_towns_vermont",
        "default_type": "town",
    },
    {
        "url": "https://en.wikipedia.org/wiki/List_of_ghost_towns_in_Virginia",
        "source": "wikipedia:ghost_towns_virginia",
        "default_type": "town",
    },
    {
        "url": "https://en.wikipedia.org/wiki/List_of_ghost_towns_in_West_Virginia",
        "source": "wikipedia:ghost_towns_west_virginia",
        "default_type": "town",
    },
    {
        "url": "https://en.wikipedia.org/wiki/List_of_ghost_towns_in_Wisconsin",
        "source": "wikipedia:ghost_towns_wisconsin",
        "default_type": "town",
    },
    # ------------------------------------------------------------------
    # Old / defunct railroads
    # ------------------------------------------------------------------
    {
        "url": "https://en.wikipedia.org/wiki/List_of_defunct_railroads_of_the_United_States",
        "source": "wikipedia:defunct_railroads",
        "default_type": "railroad_stop",
    },
    {
        "url": "https://en.wikipedia.org/wiki/List_of_defunct_United_States_railroads_(A)",
        "source": "wikipedia:defunct_railroads_a",
        "default_type": "railroad_stop",
    },
    {
        "url": "https://en.wikipedia.org/wiki/List_of_defunct_United_States_railroads_(B)",
        "source": "wikipedia:defunct_railroads_b",
        "default_type": "railroad_stop",
    },
    {
        "url": "https://en.wikipedia.org/wiki/List_of_defunct_United_States_railroads_(C)",
        "source": "wikipedia:defunct_railroads_c",
        "default_type": "railroad_stop",
    },
    {
        "url": "https://en.wikipedia.org/wiki/List_of_defunct_United_States_railroads_(D)",
        "source": "wikipedia:defunct_railroads_d",
        "default_type": "railroad_stop",
    },
    {
        "url": "https://en.wikipedia.org/wiki/List_of_defunct_United_States_railroads_(E%E2%80%93H)",
        "source": "wikipedia:defunct_railroads_e_h",
        "default_type": "railroad_stop",
    },
    {
        "url": "https://en.wikipedia.org/wiki/List_of_defunct_United_States_railroads_(I%E2%80%93L)",
        "source": "wikipedia:defunct_railroads_i_l",
        "default_type": "railroad_stop",
    },
    {
        "url": "https://en.wikipedia.org/wiki/List_of_defunct_United_States_railroads_(M)",
        "source": "wikipedia:defunct_railroads_m",
        "default_type": "railroad_stop",
    },
    {
        "url": "https://en.wikipedia.org/wiki/List_of_defunct_United_States_railroads_(N%E2%80%93R)",
        "source": "wikipedia:defunct_railroads_n_r",
        "default_type": "railroad_stop",
    },
    {
        "url": "https://en.wikipedia.org/wiki/List_of_defunct_United_States_railroads_(S)",
        "source": "wikipedia:defunct_railroads_s",
        "default_type": "railroad_stop",
    },
    {
        "url": "https://en.wikipedia.org/wiki/List_of_defunct_United_States_railroads_(T%E2%80%93Z)",
        "source": "wikipedia:defunct_railroads_t_z",
        "default_type": "railroad_stop",
    },
    {
        "url": "https://en.wikipedia.org/wiki/List_of_narrow-gauge_railroads",
        "source": "wikipedia:narrow_gauge_railroads",
        "default_type": "railroad_stop",
    },
    {
        "url": "https://en.wikipedia.org/wiki/Transcontinental_railroad",
        "source": "wikipedia:transcontinental_railroad",
        "default_type": "railroad_stop",
    },
    # ------------------------------------------------------------------
    # Stagecoach routes & stops (additional, not in first script)
    # ------------------------------------------------------------------
    {
        "url": "https://en.wikipedia.org/wiki/Wells_Fargo",
        "source": "wikipedia:stagecoach_wells_fargo",
        "default_type": "stagecoach_stop",
    },
    {
        "url": "https://en.wikipedia.org/wiki/Holladay_Overland_Mail_and_Express_Company",
        "source": "wikipedia:stagecoach_holladay",
        "default_type": "stagecoach_stop",
    },
    {
        "url": "https://en.wikipedia.org/wiki/San_Antonio%E2%80%93San_Diego_Mail_Line",
        "source": "wikipedia:stagecoach_sa_sd_mail",
        "default_type": "stagecoach_stop",
    },
    {
        "url": "https://en.wikipedia.org/wiki/Concord_stagecoach",
        "source": "wikipedia:stagecoach_concord",
        "default_type": "stagecoach_stop",
    },
    {
        "url": "https://en.wikipedia.org/wiki/Jackass_Mail",
        "source": "wikipedia:stagecoach_jackass_mail",
        "default_type": "stagecoach_stop",
    },
    # ------------------------------------------------------------------
    # Historic settlements & old communities
    # ------------------------------------------------------------------
    {
        "url": "https://en.wikipedia.org/wiki/List_of_former_municipalities_in_the_United_States",
        "source": "wikipedia:former_municipalities",
        "default_type": "town",
    },
    {
        "url": "https://en.wikipedia.org/wiki/List_of_unincorporated_communities_in_the_United_States",
        "source": "wikipedia:unincorporated_communities",
        "default_type": "town",
    },
    # ------------------------------------------------------------------
    # Gold rush sites
    # ------------------------------------------------------------------
    {
        "url": "https://en.wikipedia.org/wiki/California_Gold_Rush",
        "source": "wikipedia:gold_rush_california",
        "default_type": "mine",
    },
    {
        "url": "https://en.wikipedia.org/wiki/Klondike_Gold_Rush",
        "source": "wikipedia:gold_rush_klondike",
        "default_type": "mine",
    },
    {
        "url": "https://en.wikipedia.org/wiki/Pike%27s_Peak_Gold_Rush",
        "source": "wikipedia:gold_rush_pikes_peak",
        "default_type": "mine",
    },
    {
        "url": "https://en.wikipedia.org/wiki/Colorado_Gold_Rush",
        "source": "wikipedia:gold_rush_colorado",
        "default_type": "mine",
    },
    {
        "url": "https://en.wikipedia.org/wiki/Georgia_Gold_Rush",
        "source": "wikipedia:gold_rush_georgia",
        "default_type": "mine",
    },
    {
        "url": "https://en.wikipedia.org/wiki/Black_Hills_Gold_Rush",
        "source": "wikipedia:gold_rush_black_hills",
        "default_type": "mine",
    },
    {
        "url": "https://en.wikipedia.org/wiki/Montana_Gold_Rush",
        "source": "wikipedia:gold_rush_montana",
        "default_type": "mine",
    },
    {
        "url": "https://en.wikipedia.org/wiki/Boise_Basin_gold_rush",
        "source": "wikipedia:gold_rush_boise_basin",
        "default_type": "mine",
    },
    # ------------------------------------------------------------------
    # Old mines
    # ------------------------------------------------------------------
    {
        "url": "https://en.wikipedia.org/wiki/List_of_mines_in_the_United_States",
        "source": "wikipedia:mines_us",
        "default_type": "mine",
    },
    {
        "url": "https://en.wikipedia.org/wiki/Mining_in_the_United_States",
        "source": "wikipedia:mining_us",
        "default_type": "mine",
    },
    # ------------------------------------------------------------------
    # Wagon and emigrant trails (not already covered)
    # ------------------------------------------------------------------
    {
        "url": "https://en.wikipedia.org/wiki/Bozeman_Trail",
        "source": "wikipedia:bozeman_trail",
        "default_type": "trail",
    },
    {
        "url": "https://en.wikipedia.org/wiki/Chisholm_Trail",
        "source": "wikipedia:chisholm_trail",
        "default_type": "trail",
    },
    {
        "url": "https://en.wikipedia.org/wiki/Goodnight%E2%80%93Loving_Trail",
        "source": "wikipedia:goodnight_loving_trail",
        "default_type": "trail",
    },
    {
        "url": "https://en.wikipedia.org/wiki/Great_Western_Cattle_Trail",
        "source": "wikipedia:great_western_cattle_trail",
        "default_type": "trail",
    },
    {
        "url": "https://en.wikipedia.org/wiki/Wilderness_Road",
        "source": "wikipedia:wilderness_road",
        "default_type": "trail",
    },
    {
        "url": "https://en.wikipedia.org/wiki/Braddock%27s_Road",
        "source": "wikipedia:braddocks_road",
        "default_type": "trail",
    },
    {
        "url": "https://en.wikipedia.org/wiki/Forbes_Road",
        "source": "wikipedia:forbes_road",
        "default_type": "trail",
    },
    {
        "url": "https://en.wikipedia.org/wiki/National_Road",
        "source": "wikipedia:national_road",
        "default_type": "trail",
    },
    {
        "url": "https://en.wikipedia.org/wiki/Anza_Trail",
        "source": "wikipedia:anza_trail",
        "default_type": "trail",
    },
    {
        "url": "https://en.wikipedia.org/wiki/Gila_River_Trail",
        "source": "wikipedia:gila_river_trail",
        "default_type": "trail",
    },
    {
        "url": "https://en.wikipedia.org/wiki/Cooke%27s_Wagon_Road",
        "source": "wikipedia:cookes_wagon_road",
        "default_type": "trail",
    },
    {
        "url": "https://en.wikipedia.org/wiki/Smoky_Hill_Trail",
        "source": "wikipedia:smoky_hill_trail",
        "default_type": "trail",
    },
    {
        "url": "https://en.wikipedia.org/wiki/Lander_Road",
        "source": "wikipedia:lander_road",
        "default_type": "trail",
    },
    # ------------------------------------------------------------------
    # Frontier-era battles (not already covered)
    # ------------------------------------------------------------------
    {
        "url": "https://en.wikipedia.org/wiki/List_of_conflicts_in_the_United_States",
        "source": "wikipedia:us_conflicts",
        "default_type": "battle",
    },
    {
        "url": "https://en.wikipedia.org/wiki/American_frontier",
        "source": "wikipedia:american_frontier",
        "default_type": "battle",
    },
    {
        "url": "https://en.wikipedia.org/wiki/French_and_Indian_War",
        "source": "wikipedia:french_indian_war",
        "default_type": "battle",
    },
    # ------------------------------------------------------------------
    # Ferries & river crossings (additional)
    # ------------------------------------------------------------------
    {
        "url": "https://en.wikipedia.org/wiki/List_of_ferries_across_the_Missouri_River",
        "source": "wikipedia:ferries_missouri_river",
        "default_type": "ferry",
    },
    {
        "url": "https://en.wikipedia.org/wiki/List_of_crossings_of_the_Ohio_River",
        "source": "wikipedia:crossings_ohio_river",
        "default_type": "ferry",
    },
    {
        "url": "https://en.wikipedia.org/wiki/List_of_crossings_of_the_Mississippi_River",
        "source": "wikipedia:crossings_mississippi_river",
        "default_type": "ferry",
    },
    # ------------------------------------------------------------------
    # Old cemeteries
    # ------------------------------------------------------------------
    {
        "url": "https://en.wikipedia.org/wiki/List_of_cemeteries_in_the_United_States",
        "source": "wikipedia:cemeteries_us",
        "default_type": "cemetery",
    },
    # ------------------------------------------------------------------
    # Missions (additional, not in first script)
    # ------------------------------------------------------------------
    {
        "url": "https://en.wikipedia.org/wiki/Spanish_missions_in_Florida",
        "source": "wikipedia:missions_florida",
        "default_type": "mission",
    },
    {
        "url": "https://en.wikipedia.org/wiki/Spanish_missions_in_Georgia",
        "source": "wikipedia:missions_georgia",
        "default_type": "mission",
    },
    {
        "url": "https://en.wikipedia.org/wiki/Spanish_missions_in_South_Carolina",
        "source": "wikipedia:missions_south_carolina",
        "default_type": "mission",
    },
    # ------------------------------------------------------------------
    # Shipwrecks — Great Lakes & coasts (additional)
    # ------------------------------------------------------------------
    {
        "url": "https://en.wikipedia.org/wiki/List_of_shipwrecks_of_the_Great_Lakes",
        "source": "wikipedia:shipwrecks_great_lakes",
        "default_type": "shipwreck",
    },
    {
        "url": "https://en.wikipedia.org/wiki/List_of_shipwrecks_of_the_Atlantic_coast_of_the_United_States",
        "source": "wikipedia:shipwrecks_atlantic",
        "default_type": "shipwreck",
    },
    {
        "url": "https://en.wikipedia.org/wiki/List_of_shipwrecks_of_the_Pacific_coast_of_the_United_States",
        "source": "wikipedia:shipwrecks_pacific",
        "default_type": "shipwreck",
    },
]


# ---------------------------------------------------------------------------
# Generic list parser — local wrapper that resolves default_type from
# WIKIPEDIA_PAGES_2 instead of the original WIKIPEDIA_PAGES list.
# ---------------------------------------------------------------------------

def _parse_generic_list_page_2(soup: BeautifulSoup, source: str) -> list:
    """
    Wrapper around the original ``_parse_generic_list_page`` that resolves
    ``default_type`` from :data:`WIKIPEDIA_PAGES_2` rather than the first
    module's ``WIKIPEDIA_PAGES`` list.

    The original function iterates over ``WIKIPEDIA_PAGES`` to find the
    matching source key; sources defined only in ``WIKIPEDIA_PAGES_2`` would
    not be found there, causing the ``default_type`` to fall back to the
    generic ``"structure"`` value.  This wrapper patches the lookup by
    temporarily injecting an entry with the correct ``default_type`` into the
    records returned by the original parser.
    """
    # Determine the intended default_type from our own page list.
    intended_type = "structure"
    for page_config in WIKIPEDIA_PAGES_2:
        if page_config["source"] == source:
            intended_type = page_config.get("default_type", "structure")
            break

    records = _parse_generic_list_page_orig(soup, source)

    # Patch any record whose default_type resolved to the generic fallback.
    for rec in records:
        if rec.get("default_type") in (None, "structure"):
            rec["default_type"] = intended_type

    return records


# ---------------------------------------------------------------------------
# Parser dispatch table
# ---------------------------------------------------------------------------

_PAGE_PARSERS_2 = {
    # Ghost towns — remaining states
    "wikipedia:ghost_towns_connecticut": _parse_ghost_towns_page,
    "wikipedia:ghost_towns_delaware": _parse_ghost_towns_page,
    "wikipedia:ghost_towns_florida": _parse_ghost_towns_page,
    "wikipedia:ghost_towns_georgia": _parse_ghost_towns_page,
    "wikipedia:ghost_towns_hawaii": _parse_ghost_towns_page,
    "wikipedia:ghost_towns_illinois": _parse_ghost_towns_page,
    "wikipedia:ghost_towns_indiana": _parse_ghost_towns_page,
    "wikipedia:ghost_towns_iowa": _parse_ghost_towns_page,
    "wikipedia:ghost_towns_kentucky": _parse_ghost_towns_page,
    "wikipedia:ghost_towns_louisiana": _parse_ghost_towns_page,
    "wikipedia:ghost_towns_maine": _parse_ghost_towns_page,
    "wikipedia:ghost_towns_maryland": _parse_ghost_towns_page,
    "wikipedia:ghost_towns_massachusetts": _parse_ghost_towns_page,
    "wikipedia:ghost_towns_michigan": _parse_ghost_towns_page,
    "wikipedia:ghost_towns_minnesota": _parse_ghost_towns_page,
    "wikipedia:ghost_towns_mississippi": _parse_ghost_towns_page,
    "wikipedia:ghost_towns_missouri": _parse_ghost_towns_page,
    "wikipedia:ghost_towns_new_hampshire": _parse_ghost_towns_page,
    "wikipedia:ghost_towns_new_jersey": _parse_ghost_towns_page,
    "wikipedia:ghost_towns_new_york": _parse_ghost_towns_page,
    "wikipedia:ghost_towns_north_carolina": _parse_ghost_towns_page,
    "wikipedia:ghost_towns_ohio": _parse_ghost_towns_page,
    "wikipedia:ghost_towns_pennsylvania": _parse_ghost_towns_page,
    "wikipedia:ghost_towns_rhode_island": _parse_ghost_towns_page,
    "wikipedia:ghost_towns_south_carolina": _parse_ghost_towns_page,
    "wikipedia:ghost_towns_tennessee": _parse_ghost_towns_page,
    "wikipedia:ghost_towns_vermont": _parse_ghost_towns_page,
    "wikipedia:ghost_towns_virginia": _parse_ghost_towns_page,
    "wikipedia:ghost_towns_west_virginia": _parse_ghost_towns_page,
    "wikipedia:ghost_towns_wisconsin": _parse_ghost_towns_page,
    # Old / defunct railroads
    "wikipedia:defunct_railroads": _parse_generic_list_page_2,
    "wikipedia:defunct_railroads_a": _parse_generic_list_page_2,
    "wikipedia:defunct_railroads_b": _parse_generic_list_page_2,
    "wikipedia:defunct_railroads_c": _parse_generic_list_page_2,
    "wikipedia:defunct_railroads_d": _parse_generic_list_page_2,
    "wikipedia:defunct_railroads_e_h": _parse_generic_list_page_2,
    "wikipedia:defunct_railroads_i_l": _parse_generic_list_page_2,
    "wikipedia:defunct_railroads_m": _parse_generic_list_page_2,
    "wikipedia:defunct_railroads_n_r": _parse_generic_list_page_2,
    "wikipedia:defunct_railroads_s": _parse_generic_list_page_2,
    "wikipedia:defunct_railroads_t_z": _parse_generic_list_page_2,
    "wikipedia:narrow_gauge_railroads": _parse_generic_list_page_2,
    "wikipedia:transcontinental_railroad": _parse_generic_list_page_2,
    # Stagecoach routes
    "wikipedia:stagecoach_wells_fargo": _parse_generic_list_page_2,
    "wikipedia:stagecoach_holladay": _parse_generic_list_page_2,
    "wikipedia:stagecoach_sa_sd_mail": _parse_generic_list_page_2,
    "wikipedia:stagecoach_concord": _parse_generic_list_page_2,
    "wikipedia:stagecoach_jackass_mail": _parse_generic_list_page_2,
    # Historic settlements
    "wikipedia:former_municipalities": _parse_ghost_towns_page,
    "wikipedia:unincorporated_communities": _parse_ghost_towns_page,
    # Gold rush
    "wikipedia:gold_rush_california": _parse_generic_list_page_2,
    "wikipedia:gold_rush_klondike": _parse_generic_list_page_2,
    "wikipedia:gold_rush_pikes_peak": _parse_generic_list_page_2,
    "wikipedia:gold_rush_colorado": _parse_generic_list_page_2,
    "wikipedia:gold_rush_georgia": _parse_generic_list_page_2,
    "wikipedia:gold_rush_black_hills": _parse_generic_list_page_2,
    "wikipedia:gold_rush_montana": _parse_generic_list_page_2,
    "wikipedia:gold_rush_boise_basin": _parse_generic_list_page_2,
    # Old mines
    "wikipedia:mines_us": _parse_generic_list_page_2,
    "wikipedia:mining_us": _parse_generic_list_page_2,
    # Wagon / emigrant trails
    "wikipedia:bozeman_trail": _parse_trails_page,
    "wikipedia:chisholm_trail": _parse_trails_page,
    "wikipedia:goodnight_loving_trail": _parse_trails_page,
    "wikipedia:great_western_cattle_trail": _parse_trails_page,
    "wikipedia:wilderness_road": _parse_trails_page,
    "wikipedia:braddocks_road": _parse_trails_page,
    "wikipedia:forbes_road": _parse_trails_page,
    "wikipedia:national_road": _parse_trails_page,
    "wikipedia:anza_trail": _parse_trails_page,
    "wikipedia:gila_river_trail": _parse_trails_page,
    "wikipedia:cookes_wagon_road": _parse_trails_page,
    "wikipedia:smoky_hill_trail": _parse_trails_page,
    "wikipedia:lander_road": _parse_trails_page,
    # Frontier-era battles
    "wikipedia:us_conflicts": _parse_battles_page,
    "wikipedia:american_frontier": _parse_battles_page,
    "wikipedia:french_indian_war": _parse_battles_page,
    # Ferries & river crossings
    "wikipedia:ferries_missouri_river": _parse_generic_list_page_2,
    "wikipedia:crossings_ohio_river": _parse_generic_list_page_2,
    "wikipedia:crossings_mississippi_river": _parse_generic_list_page_2,
    # Old cemeteries
    "wikipedia:cemeteries_us": _parse_generic_list_page_2,
    # Missions
    "wikipedia:missions_florida": _parse_generic_list_page_2,
    "wikipedia:missions_georgia": _parse_generic_list_page_2,
    "wikipedia:missions_south_carolina": _parse_generic_list_page_2,
    # Shipwrecks
    "wikipedia:shipwrecks_great_lakes": _parse_generic_list_page_2,
    "wikipedia:shipwrecks_atlantic": _parse_generic_list_page_2,
    "wikipedia:shipwrecks_pacific": _parse_generic_list_page_2,
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def scrape_source_2(
    page_config: Dict[str, str],
    geocode_missing: bool = True,
    timeout: float = 30.0,
) -> List[Dict[str, Any]]:
    """
    Scrape and normalise a single Wikipedia page config entry from
    :data:`WIKIPEDIA_PAGES_2`.

    Identical in structure to :func:`app.scrapers.wikipedia.scrape_source`
    but dispatches via :data:`_PAGE_PARSERS_2`.

    Args:
        page_config:     A single entry from :data:`WIKIPEDIA_PAGES_2`.
        geocode_missing: If ``True``, attempt to geocode records that lack
                         explicit coordinates.
        timeout:         HTTP timeout in seconds.

    Returns:
        List of finalised record dicts for this source.
    """
    url = page_config["url"]
    source = page_config["source"]
    logger.info("Fetching %s", url)

    async with httpx.AsyncClient(timeout=timeout) as client:
        soup = await _fetch_page(client, url)

    if soup is None:
        return []

    parser = _PAGE_PARSERS_2.get(source)
    if parser is None:
        logger.warning("No parser registered for source %r", source)
        return []

    records = parser(soup, source)

    if geocode_missing:
        records = await _enrich_with_geocoding(records)

    finalised: List[Dict[str, Any]] = []
    for rec in records:
        if is_blocked(rec["name"], rec.get("description", "")):
            logger.debug("Blocked record: %r", rec["name"])
            continue

        event_type = classify_event_type(rec["name"], rec.get("description", ""))
        default_type = rec.get("default_type", "event")

        if default_type not in _GENERIC_DEFAULT_TYPES:
            event_type = default_type
        elif event_type == "event":
            event_type = default_type

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

    logger.info("Scraped and normalised %d records from %s", len(finalised), url)
    return finalised


async def _fetch_and_parse_2(
    client: httpx.AsyncClient,
    page_config: Dict[str, str],
) -> List[Dict[str, Any]]:
    """
    Fetch a single Wikipedia page from :data:`WIKIPEDIA_PAGES_2` and parse it.

    No geocoding or final normalisation is performed here.
    """
    url = page_config["url"]
    source = page_config["source"]
    logger.info("Fetching %s", url)

    soup = await _fetch_page(client, url)
    if soup is None:
        return []

    parser = _PAGE_PARSERS_2.get(source)
    if parser is None:
        logger.warning("No parser registered for source %r", source)
        return []

    return parser(soup, source)


async def scrape_all_2(
    geocode_missing: bool = True,
    timeout: float = 30.0,
) -> List[Dict[str, Any]]:
    """
    Scrape all pages in :data:`WIKIPEDIA_PAGES_2` concurrently and return
    normalised records.

    Identical in structure to :func:`app.scrapers.wikipedia.scrape_all`
    but operates on :data:`WIKIPEDIA_PAGES_2` and :data:`_PAGE_PARSERS_2`.

    Args:
        geocode_missing: If ``True``, attempt to geocode records that lack
                         explicit coordinates.
        timeout:         HTTP timeout in seconds.

    Returns:
        List of record dicts ready for database insertion.
    """
    async with httpx.AsyncClient(timeout=timeout) as client:
        fetch_results = await asyncio.gather(
            *(_fetch_and_parse_2(client, page_config) for page_config in WIKIPEDIA_PAGES_2),
            return_exceptions=True,
        )

    raw_records: List[Dict[str, Any]] = []
    for page_config, result in zip(WIKIPEDIA_PAGES_2, fetch_results):
        if isinstance(result, Exception):
            logger.error(
                "Error fetching/parsing %s: %s",
                page_config["source"],
                result,
            )
        else:
            raw_records.extend(result)

    if geocode_missing:
        raw_records = await _enrich_with_geocoding(raw_records)

    finalised: List[Dict[str, Any]] = []
    for rec in raw_records:
        if is_blocked(rec["name"], rec.get("description", "")):
            logger.debug("Blocked record: %r", rec["name"])
            continue

        event_type = classify_event_type(rec["name"], rec.get("description", ""))
        default_type = rec.get("default_type", "event")

        if default_type not in _GENERIC_DEFAULT_TYPES:
            event_type = default_type
        elif event_type == "event":
            event_type = default_type

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
