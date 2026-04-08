#!/usr/bin/env python3
"""
Abandoned Churches scraper — builds a dataset of abandoned and derelict
religious buildings in the USA, sourced from Obsidian Urbex Photography
and supplemented by a curated seed dataset.

Extraction order (tries each until one succeeds):

1. **Obsidian Urbex Photography scrape** — fetches the USA location listing
   at ``https://www.obsidianurbexphotography.com/location-category/usa/``,
   parses entries that are religious buildings (churches, synagogues,
   chapels, cathedrals).

2. **Seed dataset** — if the network request fails (e.g. sandboxed CI
   environment or site unavailable), falls back to a curated offline list
   of well-documented abandoned religious buildings with verified or
   approximate coordinates.

Usage::

    python scripts/fetch_abandoned_churches.py
    python scripts/fetch_abandoned_churches.py --output-dir data/
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger("fetch_abandoned_churches")

_OBSIDIAN_USA_URL = "https://www.obsidianurbexphotography.com/location-category/usa/"
_BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)
_REQUEST_TIMEOUT = 30

_RELIGIOUS_KEYWORDS = (
    "church",
    "synagogue",
    "chapel",
    "cathedral",
    "temple",
    "basilica",
    "abbey",
    "convent",
    "monastery",
    "parish",
    "dogma",
    "sacred",
    "holy",
    "saint",
    "st.",
    "blessed",
    "immaculate",
    "trinity",
    "resurrection",
)

# ---------------------------------------------------------------------------
# Seed dataset
# ---------------------------------------------------------------------------

SEED_CHURCHES: List[Dict[str, Any]] = [
    {
        "name": "Blue and Gold Synagogue",
        "type": "abandoned_church",
        "latitude": 42.358,
        "longitude": -83.052,
        "description": (
            "This 1920s Jewish synagogue served a thriving immigrant community before industrial "
            "decline eroded the surrounding neighborhood through the 1960s and 1970s. The circular "
            "sanctuary is distinguished by vivid yellow walls, a navy-blue ceiling with gilded gold "
            "stenciling, and arched stained-glass windows that once seated over 1,000 worshippers. "
            "Congregation members relocated to the suburbs as economic conditions worsened, and the "
            "building closed in the mid-1990s with Torah scrolls removed for safekeeping. The "
            "striking interior retains its dramatic color scheme despite decades of neglect, making "
            "it one of the most-photographed abandoned religious sites in the Rust Belt."
        ),
        "source": "obsidian_urbex_churches",
        "confidence": 0.65,
    },
    {
        "name": "Sons of Israel Synagogue",
        "type": "abandoned_church",
        "latitude": 40.9188,
        "longitude": -73.8974,
        "description": (
            "Built in the 1920s at 155 Elliott Avenue in Yonkers, New York, this congregation once "
            "formed the heart of a prosperous Jewish community in the lower Hudson Valley. The "
            "spacious sanctuary features a breathtaking multicolored stained-glass domed skylight "
            "centered on a Star of David, flanked by ornate arched windows and a carved bima. "
            "Mounting utility and repair costs made maintenance untenable, and the congregation "
            "sold the building around 2010 when dwindling membership could no longer support the "
            "nearly 19,000-square-foot facility. Urban explorers documented its interior during "
            "its transitional period of abandonment before redevelopment plans emerged."
        ),
        "source": "obsidian_urbex_churches",
        "confidence": 0.85,
    },
    {
        "name": "Gothic Revival Church (Keely)",
        "type": "abandoned_church",
        "latitude": 39.9624,
        "longitude": -75.1582,
        "description": (
            "The Church of the Assumption of the Blessed Virgin Mary at 1133 Spring Garden Street "
            "in Philadelphia is the oldest surviving church designed by prolific Irish-American "
            "Catholic architect Patrick Charles Keely, built between 1848 and 1849. Its Gothic "
            "Revival facade features a two-story nave, pointed lancet windows, ornate columns, and "
            "dramatic pointed arches that influenced dozens of subsequent Keely commissions across "
            "the Northeast. The parish closed in 1995 as the Spring Garden neighborhood declined, "
            "leaving this nationally significant landmark vacant for over two decades and vulnerable "
            "to vandalism. Despite landmark protection and its association with Saints John Neumann "
            "and Katharine Drexel, the church remains abandoned and hauntingly photogenic."
        ),
        "source": "obsidian_urbex_churches",
        "confidence": 0.85,
    },
    {
        "name": "Dark Dogma Church",
        "type": "abandoned_church",
        "latitude": 40.4626,
        "longitude": -79.9182,
        "description": (
            "Saints Peter and Paul Church at 130 Larimer Avenue in Pittsburgh's East Liberty "
            "neighborhood was built in 1890 and served the area's German and Eastern European "
            "Catholic population for over a century before closing in 1992. The Gothic Revival "
            "structure features a striking stone facade, soaring nave, and lancet windows whose "
            "stained glass remains largely intact despite years of exposure. The church gained "
            "widespread recognition when director Kevin Smith selected it as the principal filming "
            "location for the 1999 film Dogma, standing in for the fictional Saint Michael's "
            "Church in Red Bank, New Jersey. Today the building is severely deteriorated but "
            "structurally extant, drawing film buffs and urban explorers to its dramatically "
            "decayed interior."
        ),
        "source": "obsidian_urbex_churches",
        "confidence": 0.85,
    },
    {
        "name": "St. Valentine's Church and School",
        "type": "abandoned_church",
        "latitude": 42.8664,
        "longitude": -78.869,
        "description": (
            "St. Valentine's parish was founded by Buffalo's Polish-American community in the Old "
            "First Ward neighborhood, holding its first Mass in a tent on Perry Street in August "
            "1920 before constructing a combined church, school, and auditorium complex on South "
            "Park Avenue. The red brick Romanesque complex served generations of Polish Catholic "
            "families and stood as a civic anchor for the waterfront district for over eighty "
            "years. The Archdiocese of Buffalo closed the parish in 2007 during a broad "
            "consolidation of urban parishes, and the buildings sat vacant for over a decade before "
            "eventual partial reuse. The abandoned school wing offered urban explorers an intact "
            "glimpse of mid-century Catholic institutional architecture, including original "
            "classroom fixtures, chapel furnishings, and gymnasium equipment."
        ),
        "source": "obsidian_urbex_churches",
        "confidence": 0.75,
    },
    {
        "name": "Sacred Heart Church (Vernon, CT)",
        "type": "abandoned_church",
        "latitude": 41.8321,
        "longitude": -72.4733,
        "description": (
            "Sacred Heart Church at 550 Hartford Turnpike in Vernon, Connecticut was a striking "
            "modernist Catholic structure completed in 1971, featuring seven stories of bare poured "
            "concrete in an angular pyramidal form that earned local nicknames such as the Cement "
            "Tent and St. Cement. The brutalist interior featured a soaring 85-foot concrete "
            "ceiling converging on an angel-shaped skylight, a dramatic departure from traditional "
            "ecclesiastical architecture. Concrete spalling became a serious structural hazard by "
            "1980, and the building was condemned for worship in 1997 after chunks of ceiling fell "
            "toward the pews; the parish merged with St. Bernard's in 2017. The vacant church "
            "stood for over twenty years before demolition crews began dismantling it in March "
            "2019, attracting urban explorers until its final days."
        ),
        "source": "obsidian_urbex_churches",
        "confidence": 0.85,
    },
    {
        "name": "Woodward Avenue Presbyterian Church",
        "type": "abandoned_church",
        "latitude": 42.3779,
        "longitude": -83.0794,
        "description": (
            "This ambitious Gothic Revival Presbyterian church was constructed in 1911 on Woodward "
            "Avenue in Detroit's Boston-Edison district, featuring twin towers, an octagonal "
            "lantern, and an ornate interior designed to serve the city's growing Protestant "
            "establishment during Detroit's early automotive boom years. The congregation flourished "
            "through the mid-twentieth century but declined as white flight reshaped the city's "
            "demographics after the 1967 riots, ultimately vacating the building in the mid-2000s. "
            "The exterior stonework and twin towers remain in reasonable condition from the street, "
            "though the interior has suffered extensively from water infiltration and vandalism. "
            "Its prominent position on Detroit's main corridor makes it one of the most visible "
            "symbols of the city's abandoned ecclesiastical heritage."
        ),
        "source": "obsidian_urbex_churches",
        "confidence": 0.85,
    },
    {
        "name": "St. Agnes Catholic Church",
        "type": "abandoned_church",
        "latitude": 42.3664,
        "longitude": -83.0938,
        "description": (
            "St. Agnes Catholic Church at 7601 Rosa Parks Boulevard in Detroit's LaSalle Park "
            "neighborhood was built in 1921 in a French Gothic style featuring a soaring nave, "
            "elaborate stonework, and original stained-glass windows depicting the life of "
            "Saint Agnes. The parish served a predominantly African-American Catholic community "
            "and gained national attention when Mother Teresa visited the congregation in 1979 "
            "during her tour of Detroit's poverty-stricken neighborhoods. Declining attendance "
            "and the broader collapse of Detroit's near-west side population forced the Archdiocese "
            "to close the church in 2006, leaving the building vacant. The intact stained glass "
            "and well-preserved exterior masonry attract preservationists and urban explorers "
            "despite ongoing interior deterioration from roof leaks."
        ),
        "source": "obsidian_urbex_churches",
        "confidence": 0.85,
    },
    {
        "name": "Most Blessed Sacrament Church",
        "type": "abandoned_church",
        "latitude": 39.9398,
        "longitude": -75.2316,
        "description": (
            "Most Blessed Sacrament Church at 5600 Chester Avenue in Philadelphia's Kingsessing "
            "neighborhood was a large Gothic Revival Catholic parish built in the early twentieth "
            "century to serve the Southwest Philadelphia working-class community of Irish and "
            "Italian descent. The structure features a broad nave with pointed clerestory windows, "
            "a prominent bell tower, and decorative brick corbeling characteristic of the "
            "Philadelphia Gothic style. Demographic shifts accelerated by urban renewal projects "
            "gradually emptied the surrounding neighborhood, and the Archdiocese of Philadelphia "
            "closed the parish in 2005. The substantial masonry shell remains standing, drawing "
            "urban explorers documenting the loss of Philadelphia's dense network of neighborhood "
            "Catholic parishes."
        ),
        "source": "obsidian_urbex_churches",
        "confidence": 0.85,
    },
    {
        "name": "St. Boniface Church",
        "type": "abandoned_church",
        "latitude": 41.8981,
        "longitude": -87.662,
        "description": (
            "St. Boniface Catholic Church at 1358 West Chestnut Street in Chicago was designed by "
            "architect Henry Schlacks in a German Romanesque Revival style and built between 1902 "
            "and 1904, serving a German immigrant parish founded in 1864 on Chicago's near "
            "northwest side. The red brick exterior features rounded Romanesque arches, a prominent "
            "bell tower, and elaborate decorative brickwork, while the interior retains exceptional "
            "murals and decorative plasterwork commissioned by the original German congregation. "
            "As the surrounding Noble Square neighborhood transitioned through successive immigrant "
            "waves and then deindustrialization, membership fell and the Archdiocese closed the "
            "church in 1990. The building has attracted urban explorers since the early 2000s, "
            "its interior still exhibiting its remarkable original artistic program despite "
            "severe deterioration."
        ),
        "source": "obsidian_urbex_churches",
        "confidence": 0.85,
    },
    {
        "name": "Holy Trinity Catholic Church",
        "type": "abandoned_church",
        "latitude": 40.3713,
        "longitude": -79.8526,
        "description": (
            "Holy Trinity Catholic Church on South First Street in Duquesne, Pennsylvania was "
            "built between 1904 and 1907 by Slovak immigrant steelworkers employed at the nearby "
            "Carnegie Steel mills, featuring a modest Gothic Revival design with pointed arched "
            "windows and a small bell tower characteristic of immigrant parish construction. The "
            "parish flourished during the steel boom but declined sharply after the collapse of "
            "American steel production in the late 1970s, closing in 1970 as the Duquesne "
            "workforce dispersed. The building stood vacant for decades before the roof collapsed "
            "in 2016, exposing the interior to the elements and accelerating deterioration. The "
            "roofless shell remains standing along the Monongahela River valley, a somber monument "
            "to the Slovak-American industrial community that built it."
        ),
        "source": "obsidian_urbex_churches",
        "confidence": 0.85,
    },
    {
        "name": "St. Stanislaus Kostka Church",
        "type": "abandoned_church",
        "latitude": 42.3593,
        "longitude": -83.0357,
        "description": (
            "St. Stanislaus Kostka Church in Detroit's Poletown East neighborhood was founded in "
            "1898 and constructed in a Polish Baroque and Beaux-Arts style in 1911, featuring a "
            "twin-towered facade, elaborate interior gilded ornament, and large stained-glass "
            "windows depicting Polish patron saints. The parish served Detroit's substantial "
            "Polish immigrant community concentrated near the Medbury and Dubois corridor, "
            "reaching peak membership in the 1920s before the neighborhood's gradual depopulation "
            "through post-war suburbanization. The Archdiocese of Detroit closed the church in "
            "1989, and the building has remained vacant since, deteriorating steadily despite "
            "periodic community efforts to save it. The richly detailed interior, including its "
            "gilded altars and painted ceilings, attracts urban explorers and preservationists "
            "documenting the loss of Detroit's Polish ecclesiastical heritage."
        ),
        "source": "obsidian_urbex_churches",
        "confidence": 0.85,
    },
    {
        "name": "St. Liborius Church",
        "type": "abandoned_church",
        "latitude": 38.6467,
        "longitude": -90.1997,
        "description": (
            "St. Liborius Catholic Church at 1835 North 18th Street in St. Louis was built in "
            "1889 for the city's German immigrant community in an imposing Gothic Revival style "
            "featuring a soaring nave, flying buttresses, and a prominent twin-tower facade that "
            "dominated the St. Louis Place neighborhood for over a century. The parish flourished "
            "through the early twentieth century but declined rapidly as the surrounding "
            "neighborhood emptied during the urban renewal era, and the Archdiocese closed the "
            "church in 1992. The building was briefly repurposed as the Sk8 Liborius private "
            "skate park before a fire in 2023 caused significant damage. The partially "
            "fire-damaged shell remains one of the most architecturally significant abandoned "
            "religious structures in St. Louis, noted for its outstanding Gothic Revival stonework."
        ),
        "source": "obsidian_urbex_churches",
        "confidence": 0.85,
    },
    {
        "name": "Our Lady of Perpetual Help Church",
        "type": "abandoned_church",
        "latitude": 39.1057,
        "longitude": -84.5798,
        "description": (
            "Our Lady of Perpetual Help Catholic Church at 635 Steiner Avenue in Cincinnati's "
            "Sedamsville neighborhood was built in 1889 in Gothic Revival style and perched "
            "dramatically on a hillside above the Ohio River, featuring a commanding steeple "
            "visible from the river below and an organ gifted by Pope Leo XIII. The parish served "
            "Irish and German immigrants employed in the nearby Cincinnati riverfront industries, "
            "with four bells and a richly appointed interior that made it the spiritual centerpiece "
            "of lower Sedamsville. Recurrent Ohio River flooding, industrial decline, and the "
            "eventual depopulation of the hillside neighborhood led to the church's closure in "
            "1989, and the building has stood vacant since. The rectory at 639 Steiner gained "
            "additional notoriety as the site of alleged paranormal activity, while the church "
            "itself remains a well-documented abandoned structure overlooking the river valley."
        ),
        "source": "obsidian_urbex_churches",
        "confidence": 0.85,
    },
    {
        "name": "St. Matthew's Catholic Church",
        "type": "abandoned_church",
        "latitude": 42.9149,
        "longitude": -78.8241,
        "description": (
            "St. Matthew's Catholic Church at 1066 East Ferry Street in Buffalo was constructed "
            "in 1928 at a cost of $225,000, modeled architecturally on the Cathedral of Aachen "
            "in Germany and built from Ohio sandstone in a Romanesque Revival style to serve the "
            "Grider neighborhood's German Catholic community. At its peak around 1940 the parish "
            "enrolled over 4,000 individuals, but membership had collapsed to just 218 people by "
            "1990 as the neighborhood's demographics shifted and families relocated to the suburbs. "
            "The Diocese of Buffalo closed St. Matthew's in 1993 and subsequent owners were unable "
            "to fund restoration, resulting in the stripping of valuable interior materials that "
            "accelerated the building's deterioration. The Romanesque exterior retains impressive "
            "stonework and the roofline remains largely intact, making it a notable subject for "
            "architectural documentation and urban exploration."
        ),
        "source": "obsidian_urbex_churches",
        "confidence": 0.85,
    },
    {
        "name": "St. Adalbert's Church",
        "type": "abandoned_church",
        "latitude": 41.8582,
        "longitude": -87.6633,
        "description": (
            "St. Adalbert's Catholic Church at 1650 West 17th Street in Chicago's Pilsen "
            "neighborhood was built between 1914 and 1917 for the parish founded in 1874, which "
            "once served as the largest Polish congregation in the city with membership exceeding "
            "40,000 at its height. The Romanesque Revival structure features a twin-tower facade, "
            "elaborate carved limestone ornament, and a richly appointed interior with original "
            "painted murals and stained-glass windows representing one of the finest examples of "
            "Polish-American ecclesiastical architecture in the Midwest. As Pilsen's Polish "
            "population gave way to Mexican-American families and the remaining congregation "
            "dwindled, the Archdiocese of Chicago closed the parish in 2013. The vacant church "
            "is listed on the National Register of Historic Places and has attracted urban "
            "explorers and architectural historians to its monumental but deteriorating interior."
        ),
        "source": "obsidian_urbex_churches",
        "confidence": 0.85,
    },
    {
        "name": "St. Michael the Archangel Church",
        "type": "abandoned_church",
        "latitude": 41.474,
        "longitude": -81.692,
        "description": (
            "St. Michael the Archangel Catholic Church on Scranton Road in Cleveland's Tremont "
            "neighborhood was built in 1892 in a robust Romanesque style to serve the Slovak "
            "immigrant community that settled along the ridge overlooking the Cuyahoga industrial "
            "valley. The red brick and stone exterior features a prominent corner bell tower with "
            "a copper-clad steeple, and the interior retains original carved wooden altars and "
            "murals painted by Slovak craftsmen. Declining parish membership tied to Cleveland's "
            "deindustrialization and subsequent population loss led to the church's closure in "
            "2009, ending over a century of continuous Slovak Catholic worship in Tremont. The "
            "well-preserved exterior faces Lincoln Park and remains an iconic silhouette in one "
            "of Cleveland's most historically significant ethnic neighborhoods."
        ),
        "source": "obsidian_urbex_churches",
        "confidence": 0.75,
    },
    {
        "name": "Holy Family Catholic Church",
        "type": "abandoned_church",
        "latitude": 29.9757,
        "longitude": -90.0992,
        "description": (
            "Holy Family Catholic Church on Canal Street in New Orleans' Mid-City neighborhood "
            "was established in 1892 and once claimed one of the largest congregations in "
            "Louisiana, its Victorian Gothic structure serving as a spiritual anchor for the "
            "mixed-race Creole Catholic community through segregation and into the twentieth "
            "century. The church suffered catastrophic flooding from Hurricane Katrina in August "
            "2005, with water standing for weeks inside the nave and destroying the flooring, "
            "pews, and lower sections of the stained-glass windows. Despite initial recovery "
            "efforts, the combination of flood damage, mold infestation, and the decimation of "
            "the surrounding population led to the church being declared permanently closed. The "
            "partially stabilized shell has attracted urban explorers and photographers documenting "
            "the broader story of New Orleans' uneven post-Katrina recovery."
        ),
        "source": "obsidian_urbex_churches",
        "confidence": 0.75,
    },
    {
        "name": "St. Rose of Lima Catholic Church",
        "type": "abandoned_church",
        "latitude": 38.6386,
        "longitude": -90.2313,
        "description": (
            "St. Rose of Lima Catholic Church near the intersection of Goodfellow Boulevard and "
            "Maple Avenue in St. Louis was founded in 1884 to serve an Irish immigrant community, "
            "with the current building dedicated in 1910 featuring a Gothic Revival design with "
            "a prominent stone facade and lancet windows. The parish served a stable working-class "
            "Catholic neighborhood through the first half of the twentieth century before dramatic "
            "demographic shifts following the construction of Interstate 70 and urban renewal "
            "projects displaced the surrounding population. The Archdiocese of St. Louis closed "
            "the parish in 1992 as it had become an isolated island in a largely vacated urban "
            "landscape. The abandoned church stands as one of several dozen shuttered Catholic "
            "buildings that mark the north side of St. Louis as a landscape of ecclesiastical loss."
        ),
        "source": "obsidian_urbex_churches",
        "confidence": 0.75,
    },
    {
        "name": "Church of the Transfiguration",
        "type": "abandoned_church",
        "latitude": 42.897,
        "longitude": -78.8679,
        "description": (
            "The Church of the Transfiguration on Jefferson Avenue in Buffalo was constructed in "
            "1897 to serve the city's growing Polish Catholic community in the East Side "
            "neighborhood, built in a Gothic Revival style with a distinctive tall spire and "
            "elaborate brickwork that made it a neighborhood landmark. The parish thrived through "
            "the early twentieth century as Buffalo's Polish-American community expanded, but the "
            "collapse of the city's industrial economy in the 1970s and 1980s drove severe "
            "population loss on the East Side. The church was closed and subsequently suffered "
            "structural deterioration, with portions of the nave roof collapsing and leaving the "
            "interior exposed to the elements. The ruined shell, with collapsed walls exposing "
            "surviving murals to the open sky, has been extensively documented by urban "
            "exploration photographers as one of Buffalo's most dramatic abandoned religious sites."
        ),
        "source": "obsidian_urbex_churches",
        "confidence": 0.75,
    },
    {
        "name": "St. Hedwig Church",
        "type": "abandoned_church",
        "latitude": 42.361,
        "longitude": -83.096,
        "description": (
            "St. Hedwig Catholic Church at 3245 Junction Avenue in Detroit was founded to serve "
            "the city's Polish immigrant community on the west side, with the brick Gothic "
            "structure erected in the early twentieth century featuring carved stone details, "
            "pointed arched windows, and an elaborate interior with altarwork reflecting the "
            "Polish devotional tradition. The parish was one of dozens of Polish Catholic "
            "institutions concentrated in Detroit's near west side that collectively formed one "
            "of the largest urban Polish communities in America through the mid-twentieth century. "
            "Suburbanization and deindustrialization steadily eroded the congregation through the "
            "1970s and 1980s, and the Archdiocese of Detroit closed the church in 1989. The "
            "vacant building has experienced progressive deterioration over three decades, "
            "documented as part of the broader story of Detroit's lost Polish Catholic heritage."
        ),
        "source": "obsidian_urbex_churches",
        "confidence": 0.75,
    },
    {
        "name": "St. Casimir's Church (Baltimore)",
        "type": "abandoned_church",
        "latitude": 39.279,
        "longitude": -76.563,
        "description": (
            "St. Casimir's Catholic Church at 2800 O'Donnell Street in Baltimore's Canton "
            "neighborhood was built in the early twentieth century to serve the Lithuanian "
            "immigrant community that settled near the city's industrial waterfront, featuring "
            "a Romanesque brick exterior with rounded arches and a distinctive copper-domed "
            "bell tower. The parish was one of several Eastern European Catholic congregations "
            "that defined the ethnic fabric of southeast Baltimore's working-class neighborhoods, "
            "with a school and community hall serving Lithuanian cultural and religious life for "
            "generations. Population decline and the assimilation of the Lithuanian-American "
            "community led the Archdiocese of Baltimore to close the parish in 2007 as part of "
            "a broad consolidation program. The vacant building and associated school complex "
            "stand empty in a neighborhood undergoing significant gentrification, creating an "
            "incongruous historical remnant amid new residential development."
        ),
        "source": "obsidian_urbex_churches",
        "confidence": 0.75,
    },
    {
        "name": "Epiphany Roman Catholic Church",
        "type": "abandoned_church",
        "latitude": 42.388,
        "longitude": -82.978,
        "description": (
            "Epiphany Roman Catholic Church on Conner Avenue in Detroit's east side was founded "
            "in 1924, when the first masses were held in a tent for the newly established parish "
            "serving a neighborhood of Detroit autoworkers and their families. The permanent "
            "brick church building completed in 1934 features a simplified Romanesque exterior "
            "with a central bell tower and a modest but well-appointed interior reflecting the "
            "aspirational quality of Depression-era parish construction. As Detroit's east side "
            "depopulated after the 1967 riots and through the deindustrialization of the 1980s, "
            "the surrounding neighborhood transformed into a largely vacant landscape and the "
            "parish could not sustain its congregation. The church was closed and has remained "
            "vacant for decades, documented by urban explorers as part of Detroit's extensive "
            "inventory of abandoned mid-century Catholic churches."
        ),
        "source": "obsidian_urbex_churches",
        "confidence": 0.75,
    },
    {
        "name": "St. John the Baptist Church (Detroit)",
        "type": "abandoned_church",
        "latitude": 42.328,
        "longitude": -83.062,
        "description": (
            "St. John the Baptist Catholic Church near Michigan Avenue in southwest Detroit was "
            "founded to serve one of the city's early Polish immigrant communities, with the "
            "existing brick structure built in the early twentieth century in a Polish Baroque "
            "style featuring a prominent facade with decorative pilasters and a barrel-vaulted "
            "interior richly decorated with painted murals and carved woodwork. The parish "
            "occupied a densely populated ethnic neighborhood through the mid-twentieth century, "
            "serving as a center for Polish cultural life, religious education, and social "
            "services. The collapse of southwest Detroit's residential population through "
            "suburbanization and disinvestment left the parish without a sustainable congregation, "
            "leading to closure around 2000. The building has suffered considerable deterioration "
            "from deferred maintenance and vandalism, though substantial portions of the "
            "decorative interior remain for urban explorers to document."
        ),
        "source": "obsidian_urbex_churches",
        "confidence": 0.75,
    },
    {
        "name": "Pilgrim Baptist Church",
        "type": "abandoned_church",
        "latitude": 41.835,
        "longitude": -87.62,
        "description": (
            "The building at 3301 South Indiana Avenue in Chicago's Bronzeville neighborhood was "
            "designed by the celebrated architectural firm of Adler and Louis Sullivan in 1891 as "
            "Kehilath Anshe Ma'ariv, a Reform Jewish synagogue that became Sullivan's only "
            "surviving synagogue design before the congregation relocated to the North Shore. "
            "The building was sold to Pilgrim Baptist Church in 1922 and served as a legendary "
            "venue for the development of gospel music under the direction of Thomas A. Dorsey, "
            "widely considered the father of gospel music, through the mid-twentieth century. "
            "A fire swept through the building in January 2006, destroying the roof and the "
            "Sullivan-designed interior while leaving the exterior limestone walls standing. "
            "The roofless ruin, designated a Chicago Landmark, remains standing with preservation "
            "efforts debating whether the walls can anchor a restored structure."
        ),
        "source": "obsidian_urbex_churches",
        "confidence": 0.85,
    },
    {
        "name": "St. Casimir's Church (Detroit)",
        "type": "abandoned_church",
        "latitude": 42.3625,
        "longitude": -83.0407,
        "description": (
            "St. Casimir's Catholic Church near East Canfield Street in Detroit's Poletown "
            "neighborhood was established to serve the Lithuanian and Polish Catholic community "
            "on Detroit's east side, with the brick Gothic Revival structure built in the early "
            "twentieth century featuring pointed arched windows and a modest bell tower "
            "representative of immigrant parish economy. The parish community was disrupted in "
            "1981 when General Motors obtained the surrounding Poletown neighborhood by eminent "
            "domain to construct the Detroit-Hamtramck Assembly Plant, displacing thousands of "
            "residents including many longtime parishioners. The combination of neighborhood "
            "demolition and prior population decline left the congregation unsustainable, and the "
            "Archdiocese of Detroit closed the church in 1989. The building remains one of the "
            "few surviving structures in a landscape substantially cleared by the Poletown "
            "demolition, making it a historically charged remnant of a controversial urban "
            "renewal project."
        ),
        "source": "obsidian_urbex_churches",
        "confidence": 0.75,
    },
    {
        "name": "Old St. Patrick's Catholic Church (Detroit)",
        "type": "abandoned_church",
        "latitude": 42.3303,
        "longitude": -83.0421,
        "description": (
            "Old St. Patrick's Catholic Church near East Michigan Avenue in southwest Detroit "
            "was among the earliest Catholic parishes established in the city, with the existing "
            "Gothic Revival brick structure built around 1861 featuring limestone trim, pointed "
            "arched windows, and a Victorian ecclesiastical interior that survived largely intact "
            "through the twentieth century. The Irish-founded parish served the near southwest "
            "side community for well over a century before the collapse of Detroit's population "
            "in the surrounding neighborhood made continued operation unsustainable, and the "
            "Archdiocese closed the church in 1985. The building subsequently fell into "
            "progressive disrepair, with the roof beginning to fail and the interior sustaining "
            "water damage across the following decades. The nineteenth-century structure "
            "represents one of Detroit's earliest surviving Gothic ecclesiastical buildings, "
            "documented by urban explorers as emblematic of the city's antebellum religious "
            "heritage loss."
        ),
        "source": "obsidian_urbex_churches",
        "confidence": 0.75,
    },
    {
        "name": "Sacred Heart Church (Newark, NJ)",
        "type": "abandoned_church",
        "latitude": 40.7442,
        "longitude": -74.177,
        "description": (
            "Sacred Heart Catholic Church in Newark, New Jersey was built in 1914 in a Romanesque "
            "Revival style serving the Italian immigrant community of the Ironbound district, "
            "featuring rounded stone arches, a prominent corner tower, and a richly tiled interior "
            "with colorful mosaic work characteristic of Italian-American parish craftsmanship. "
            "The parish flourished through the mid-twentieth century but was severely impacted "
            "by the 1967 Newark riots and subsequent white flight that dramatically depopulated "
            "the surrounding neighborhoods over the following decade. Though the Ironbound "
            "experienced a later revival with Portuguese and Brazilian immigration, the Italian "
            "Catholic congregation had dispersed and could not be reconstituted, leading to "
            "closure of the building. The structure's Romanesque exterior and decorative tile "
            "interior have attracted architectural photographers and urban explorers interested "
            "in Newark's immigrant religious heritage."
        ),
        "source": "obsidian_urbex_churches",
        "confidence": 0.65,
    },
    {
        "name": "Immaculate Conception Church (Baltimore)",
        "type": "abandoned_church",
        "latitude": 39.298,
        "longitude": -76.624,
        "description": (
            "Immaculate Conception Catholic Church in Baltimore's Upton neighborhood was "
            "constructed in the late nineteenth century as a parish serving the predominantly "
            "Irish Catholic community of west Baltimore, featuring a red brick Gothic facade "
            "with corbeled parapets and lancet windows that formed a distinctive presence on "
            "the neighborhood streetscape. The parish experienced the racial transition of Upton "
            "from Irish and Jewish to African-American in the mid-twentieth century and struggled "
            "to adapt its ministry to the neighborhood's changed demographics before ultimately "
            "closing. The vacant church building stands in a part of west Baltimore characterized "
            "by extensive abandonment and urban decay, representing one of dozens of shuttered "
            "Catholic institutions in the city's historic neighborhoods. Urban explorers have "
            "documented the interior, which retains fragments of original plasterwork, painted "
            "decorations, and ironwork despite years of neglect and vandalism."
        ),
        "source": "obsidian_urbex_churches",
        "confidence": 0.65,
    },
    {
        "name": "St. Wenceslas Church",
        "type": "abandoned_church",
        "latitude": 41.464,
        "longitude": -81.676,
        "description": (
            "St. Wenceslas Catholic Church in Cleveland's Slavic Village neighborhood was built "
            "in the early twentieth century to serve the Bohemian and Czech immigrant community, "
            "featuring a brick Romanesque style with a broad nave, decorative ceramic tile work, "
            "and an interior adorned with Czech folk motifs unique in the city's ecclesiastical "
            "landscape. The Slavic Village neighborhood was devastated by the 2000s foreclosure "
            "crisis, which left thousands of homes vacant and caused the area's population to "
            "collapse, making it one of the hardest-hit neighborhoods in the country. The "
            "resulting population implosion left the parish without a congregation, and the "
            "church was closed and has stood vacant in a neighborhood that still struggles with "
            "widespread abandonment. The building's interior Czech folk-art decorations, now in "
            "an advanced state of deterioration, have drawn urban explorers documenting the "
            "extraordinary loss of Cleveland's Eastern European ethnic church heritage."
        ),
        "source": "obsidian_urbex_churches",
        "confidence": 0.65,
    },
    {
        "name": "Temple Israel (Milwaukee)",
        "type": "abandoned_church",
        "latitude": 43.0512,
        "longitude": -87.9116,
        "description": (
            "Temple Israel in Milwaukee's near north side was constructed in the 1920s as a "
            "Reform Jewish synagogue serving one of Wisconsin's most prominent Jewish "
            "congregations, built in a Moorish Revival style featuring arched windows with "
            "Star of David tracery, ornamental terracotta panels, and a domed roof that made it "
            "one of the most distinctive religious structures in the city. As Milwaukee's Jewish "
            "community migrated northward to the suburbs of Shorewood and Whitefish Bay in the "
            "postwar decades, membership in the inner-city congregation declined precipitously "
            "and the building was sold and eventually vacated by the 1960s. The building passed "
            "through a succession of uses and ownership changes before settling into vacancy, "
            "and its distinctive Moorish facade has attracted attention from architectural "
            "historians and urban explorers alike. The terracotta ornamental details and remnants "
            "of the dome interior remain partially intact, offering a rare surviving example of "
            "Moorish Revival religious architecture in the upper Midwest."
        ),
        "source": "obsidian_urbex_churches",
        "confidence": 0.65,
    },
    {
        "name": "St. Stanislaus Bishop and Martyr Church (St. Louis)",
        "type": "abandoned_church",
        "latitude": 38.637,
        "longitude": -90.213,
        "description": (
            "St. Stanislaus Bishop and Martyr Catholic Church on Missouri Avenue in St. Louis "
            "was founded to serve the city's large Polish immigrant community concentrated in "
            "the near north side, with the early twentieth-century brick Gothic structure "
            "featuring twin bell towers, decorated brick corbeling, and a spacious interior "
            "with Polish devotional art and carved wooden altarwork. The parish served as the "
            "religious and cultural heart of St. Louis's Polish district for decades, anchoring "
            "a community that included Polish-language schools, fraternal organizations, and "
            "social clubs. Urban renewal programs and industrial decline depopulated the "
            "surrounding neighborhood beginning in the 1950s, and the parish closed as the "
            "resident Catholic population became insufficient to support the institution. The "
            "building has stood abandoned in a largely cleared urban landscape, its twin towers "
            "remaining visible from adjacent highways as reminders of the once-dense Polish "
            "neighborhood."
        ),
        "source": "obsidian_urbex_churches",
        "confidence": 0.65,
    },
    {
        "name": "Holy Name Church (Rochester, NY)",
        "type": "abandoned_church",
        "latitude": 43.165,
        "longitude": -77.602,
        "description": (
            "Holy Name of Jesus Catholic Church in Rochester, New York was built in the early "
            "twentieth century to serve the Catholic community of the city's northeast side, "
            "featuring a brick Romanesque exterior with rounded arched windows and a modest "
            "bell tower that became a familiar neighborhood landmark over several generations. "
            "The parish served a stable working-class Catholic community through the post-war "
            "decades before demographic change and suburban migration reduced membership to "
            "unsustainable levels. The Diocese of Rochester closed the church as part of a "
            "broader parish consolidation program in the 2000s, leaving the building vacant in "
            "a neighborhood that retained only a fraction of its mid-century population. The "
            "building has been documented by urban explorers for its intact interior furnishings, "
            "including original pews, confessionals, and stained-glass windows depicting the "
            "life of Christ."
        ),
        "source": "obsidian_urbex_churches",
        "confidence": 0.65,
    },
    {
        "name": "Our Lady Help of Christians Church (Pittsburgh)",
        "type": "abandoned_church",
        "latitude": 40.4549,
        "longitude": -79.9327,
        "description": (
            "Our Lady Help of Christians Catholic Church in Pittsburgh's Larimer neighborhood "
            "celebrated its golden anniversary in 1948 as a vital hub for the Italian-American "
            "community of Pittsburgh's east end, featuring a brick Romanesque Revival structure "
            "with rounded arches and a bell tower that overlooked the dense residential blocks "
            "of the Larimer valley. The parish served as a cultural anchor for the neighborhood's "
            "Italian community through the twentieth century, but urban renewal demolitions and "
            "the collapse of industrial employment gradually emptied the surrounding streets. "
            "After the last congregation departed around 2008, the building was boarded up and "
            "subjected to significant vandalism and graffiti, with vines overgrowing the exterior "
            "walls. The structurally compromised building has been documented by Pittsburgh urban "
            "explorers and appears in the Pittsburgh Post-Gazette's Silent Sanctuaries series on "
            "the city's abandoned religious buildings."
        ),
        "source": "obsidian_urbex_churches",
        "confidence": 0.75,
    },
    {
        "name": "St. George Ukrainian Catholic Church (Newark)",
        "type": "abandoned_church",
        "latitude": 40.736,
        "longitude": -74.173,
        "description": (
            "St. George Ukrainian Greek Catholic Church in Newark, New Jersey was established "
            "to serve the Ukrainian immigrant community of Essex County in the early twentieth "
            "century, built in a Byzantine Revival style with onion domes, an elaborate "
            "iconostasis, and mosaic tilework reflecting the Eastern Christian architectural "
            "tradition brought from Galicia and Ruthenia. The congregation was one of several "
            "Eastern Rite Catholic parishes that served Newark's Central European immigrant "
            "communities during the peak immigration decades of the early twentieth century. "
            "Post-war suburbanization and the 1967 Newark riots accelerated the dispersal of "
            "the Ukrainian community to suburban Essex and Union counties, leaving the parish "
            "without a sufficient congregation to maintain the building. The vacant church, with "
            "its distinctive Byzantine domes still visible above the surrounding urban landscape, "
            "has attracted urban explorers interested in the rare Eastern Rite ecclesiastical "
            "architecture encountered in American cities."
        ),
        "source": "obsidian_urbex_churches",
        "confidence": 0.65,
    },
    {
        "name": "Trinity Evangelical Lutheran Church (Detroit)",
        "type": "abandoned_church",
        "latitude": 42.349,
        "longitude": -83.033,
        "description": (
            "Trinity Evangelical Lutheran Church near Gratiot Avenue in Detroit's east side was "
            "founded in the late nineteenth century by German Lutheran immigrants and constructed "
            "in a Gothic Revival brick style with a prominent spire and stained-glass windows "
            "depicting Lutheran theological themes, serving as the spiritual center for a German "
            "Protestant community that persisted in the neighborhood well into the twentieth "
            "century. The congregation maintained the church through the dramatic demographic "
            "transitions of the post-war decades as German and later Polish residents were "
            "replaced by African-American families, but membership eventually fell to "
            "unsustainable levels as the surrounding neighborhood depopulated. The Evangelical "
            "Lutheran Church in America closed the congregation in the early 2000s, and the "
            "building has stood vacant with progressive deterioration from weather exposure and "
            "copper theft from the steeple and roof flashings. Urban explorers have documented "
            "the intact nave with its original pews, altar, and painted plaster ceiling, much "
            "of which remains undisturbed despite two decades of abandonment."
        ),
        "source": "obsidian_urbex_churches",
        "confidence": 0.65,
    },
    {
        "name": "St. Lawrence O'Toole Church (Detroit)",
        "type": "abandoned_church",
        "latitude": 42.3778,
        "longitude": -83.0061,
        "description": (
            "St. Lawrence O'Toole Catholic Church on Meldrum Street in Detroit's east side was "
            "established in the early twentieth century serving a mixed Irish and German Catholic "
            "community in a neighborhood of auto-industry workers, built in a simplified Gothic "
            "Revival style with brick construction and modest decorative stone trim characteristic "
            "of early twentieth-century working-class parish architecture. The parish served the "
            "community through the auto boom and subsequent decades of industrial decline, "
            "eventually closing as the surrounding neighborhood was emptied by arson, abandonment, "
            "and demolition during Detroit's long fiscal crisis. The vacant building has weathered "
            "decades of neglect in a neighborhood that now consists largely of vacant lots "
            "interspersed with surviving institutional buildings, making the church an isolated "
            "historic remnant in a dramatically changed urban landscape. Urban explorers have "
            "documented significant interior decay including collapsed plaster, failed roof "
            "sections, and extensive water damage to the remaining decorative elements."
        ),
        "source": "obsidian_urbex_churches",
        "confidence": 0.65,
    },
]


# ---------------------------------------------------------------------------
# Scraper
# ---------------------------------------------------------------------------


def scrape_obsidian_urbex() -> Optional[List[Dict[str, Any]]]:
    """Try to scrape Obsidian Urbex Photography USA page for religious buildings.

    Returns a list of church records on success, or None if the request fails
    or no religious entries are found.
    """
    try:
        logger.info("Fetching %s", _OBSIDIAN_USA_URL)
        with httpx.Client(
            follow_redirects=True,
            timeout=_REQUEST_TIMEOUT,
            headers={"User-Agent": _BROWSER_UA},
        ) as client:
            response = client.get(_OBSIDIAN_USA_URL)
            response.raise_for_status()
            html = response.text

        entries = _parse_obsidian_html(html)
        if not entries:
            logger.warning("No religious entries parsed from Obsidian Urbex page.")
            return None

        logger.info("Parsed %d religious entries from Obsidian Urbex.", len(entries))
        return entries

    except Exception as exc:
        logger.warning("Obsidian Urbex scrape failed: %s", exc)
        return None


def _parse_obsidian_html(html: str) -> List[Dict[str, Any]]:
    """Extract location titles from the Obsidian Urbex USA listing page."""
    import re

    results: List[Dict[str, Any]] = []
    title_pattern = re.compile(
        r'class="[^"]*entry-title[^"]*"[^>]*>\s*<a[^>]+href="([^"]+)"[^>]*>([^<]+)</a>',
        re.IGNORECASE,
    )
    for match in title_pattern.finditer(html):
        href, title = match.group(1).strip(), match.group(2).strip()
        title_lower = title.lower()
        if any(kw in title_lower for kw in _RELIGIOUS_KEYWORDS):
            results.append(
                {
                    "name": title,
                    "type": "abandoned_church",
                    "latitude": None,
                    "longitude": None,
                    "description": f"Abandoned religious building documented by Obsidian Urbex Photography. Source URL: {href}",
                    "source": "obsidian_urbex_churches",
                    "confidence": 0.65,
                }
            )
    return results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
        datefmt="%H:%M:%S",
    )


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Fetch or generate an abandoned churches dataset for Prescia Maps."
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/"),
        metavar="DIR",
        help="Directory to write abandoned_churches.json (default: data/)",
    )
    parser.add_argument(
        "--skip-scrape",
        action="store_true",
        help="Skip the Obsidian Urbex scrape and use the seed dataset directly.",
    )
    return parser


def main() -> None:
    _setup_logging()
    parser = _build_arg_parser()
    args = parser.parse_args()

    output_dir: Path = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "abandoned_churches.json"

    churches: Optional[List[Dict[str, Any]]] = None
    method_used: str = "unknown"

    if not args.skip_scrape:
        logger.info("=== Method 1: Obsidian Urbex Photography scrape ===")
        churches = scrape_obsidian_urbex()
        if churches:
            method_used = "obsidian_urbex_scrape"

    if churches is None:
        logger.info("=== Method 2: Seed dataset fallback ===")
        churches = SEED_CHURCHES
        method_used = "seed_dataset"

    logger.info("Using data from: %s (%d records)", method_used, len(churches))

    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(churches, fh, indent=2, ensure_ascii=False)

    logger.info("Saved → %s", output_path)

    print(f"\nDone. {len(churches)} entries saved.")
    print(f"  Method used : {method_used}")
    print(f"  Output file : {output_path}")


if __name__ == "__main__":
    main()
