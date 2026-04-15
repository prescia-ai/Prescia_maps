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
    "rectory",
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
        "source": "AURIK",
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
        "source": "AURIK",
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
        "source": "AURIK",
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
        "source": "AURIK",
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
        "source": "AURIK",
        "confidence": 0.75,
    },
    {
        "name": "Blue Church and Parish School",
        "type": "abandoned_church",
        "latitude": 42.877,
        "longitude": -78.877,
        "description": (
            "This Roman Catholic church was founded by a German immigrant community that settled "
            "in a waterfront industrial neighborhood of a large American city in the mid-nineteenth "
            "century, with the brown-stoned structure completed in the 1890s featuring a soaring "
            "nave with a cornflower blue and bright yellow painted vaulted ceiling, a carved marble "
            "altar, and hanging pendant stained-glass windows. A schoolhouse was added in the 1920s "
            "to serve the parish's growing educational needs, and the complex later transitioned to "
            "serving the large Polish Catholic community that replaced the original German "
            "congregation in the surrounding neighborhood. The schoolhouse fell vacant around 2005 "
            "and the church itself closed roughly a decade later as the diocese consolidated "
            "parishes, leaving both buildings abandoned until a sale and redevelopment approval. "
            "Plans call for the church shell to be converted to commercial and restaurant use while "
            "the convent, rectory, and school buildings become residential apartments, preserving "
            "the complex's historic facades."
        ),
        "source": "AURIK",
        "confidence": 0.65,
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
        "source": "AURIK",
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
        "source": "AURIK",
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
        "source": "AURIK",
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
        "source": "AURIK",
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
        "source": "AURIK",
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
            "parish flourished through the first half of the twentieth century, but by the late "
            "1960s the Diocese of Pittsburgh determined that deferred structural repairs exceeded "
            "available funds and opted to build a new Holy Trinity in neighboring West Mifflin "
            "instead; the Duquesne church closed in 1970 when the replacement building opened. "
            "The original structure stood vacant for nearly five decades before the roof collapsed "
            "in 2016, exposing the interior to the elements and accelerating deterioration. The "
            "roofless shell remains standing along the Monongahela River valley, a somber monument "
            "to the Slovak-American industrial community that built it."
        ),
        "source": "AURIK",
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
        "source": "AURIK",
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
        "source": "AURIK",
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
        "source": "AURIK",
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
        "source": "AURIK",
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
        "source": "AURIK",
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
        "source": "AURIK",
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
        "source": "AURIK",
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
        "source": "AURIK",
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
        "source": "AURIK",
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
        "source": "AURIK",
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
        "source": "AURIK",
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
        "source": "AURIK",
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
        "source": "AURIK",
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
        "source": "AURIK",
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
        "source": "AURIK",
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
        "source": "AURIK",
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
        "source": "AURIK",
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
        "source": "AURIK",
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
        "source": "AURIK",
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
        "source": "AURIK",
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
        "source": "AURIK",
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
        "source": "AURIK",
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
        "source": "AURIK",
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
        "source": "AURIK",
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
        "source": "AURIK",
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
        "source": "AURIK",
        "confidence": 0.65,
    },
    {
        "name": "San Isidro Church (Las Mesitas)",
        "type": "abandoned_church",
        "latitude": 37.05723,
        "longitude": -106.12697,
        "description": (
            "San Isidro Church in Las Mesitas, Conejos County, Colorado, was originally constructed "
            "in 1878 and rebuilt on donated land in 1932, serving the Hispanic Catholic agricultural "
            "community of the San Luis Valley for nearly a century as a center for worship, community "
            "gatherings, and Penitente Brotherhood devotions. The stone-walled structure was dedicated "
            "to San Isidro Labrador, the patron saint of farmers, and featured vibrantly painted "
            "stained-glass windows and a historic bell cast partly from jewelry donated by pioneer "
            "women of the valley. On November 1, 1975, a malfunctioning heater ignited a catastrophic "
            "fire that destroyed everything inside — pews, Stations of the Cross, religious vessels, "
            "and the bell — leaving only the stone exterior walls standing open to the Colorado sky. "
            "The photogenic shell of the church now serves as an informal pilgrimage site where "
            "outdoor masses and even weddings are held amid the ruins, with wildflowers growing "
            "along the former nave aisles."
        ),
        "source": "AURIK",
        "confidence": 0.85,
    },
    {
        "name": "Keota Methodist Church",
        "type": "abandoned_church",
        "latitude": 40.70278,
        "longitude": -104.07528,
        "description": (
            "The Keota Methodist Church was constructed in 1918 to serve the booming prairie "
            "homestead community of Keota on the Pawnee National Grasslands of Weld County, "
            "Colorado, built as a timber-frame structure that became the social and spiritual "
            "anchor for farmers and ranchers drawn by the Chicago, Burlington and Quincy Railroad's "
            "reach across the high plains. Keota's fate was sealed by the Dust Bowl of the 1930s, "
            "which stripped the overworked prairie soil and combined with the Great Depression to "
            "drive a steady exodus of residents; the post office closed in 1974 and the last "
            "railroad track was removed in 1982. The abandoned Methodist church survives alongside "
            "a water tower and scattered foundations as the most prominent remnant of Keota's ghost "
            "town, standing in open grassland grazed by pronghorn and cattle that roam the "
            "surrounding federal land. The church has been documented by historians and photographers "
            "as an emblem of failed homesteading on the Colorado plains, with its story contributing "
            "inspiration for James Michener's fictional settlement in the novel Centennial."
        ),
        "source": "AURIK",
        "confidence": 0.85,
    },
    {
        "name": "Antelope Springs Methodist Episcopal Church",
        "type": "abandoned_church",
        "latitude": 40.46472,
        "longitude": -103.59972,
        "description": (
            "The Antelope Springs Methodist Episcopal Church at 31948 CO-71 near Snyder, Morgan "
            "County, Colorado, was constructed in 1915 and represents one of the last surviving "
            "community-built timber-frame churches of the homestead era in northeastern Colorado, "
            "listed on the National Register of Historic Places in 2013 for its architectural "
            "integrity and its embodiment of the agricultural pioneer spirit of the region. The "
            "modest one-story frame building was hand-constructed by local settler families and "
            "served as both a worship space and community gathering hall for the scattered farms "
            "of the Antelope Springs area through the mid-twentieth century until the congregation "
            "dissolved as the rural population declined. On July 14, 2019, arsonists breached the "
            "historic church and set a fire that severely damaged the interior, destroying roof "
            "timbers and scorching the walls; two adults and a juvenile were arrested and charged "
            "with arson and trespass within days. Colorado Preservation, Inc. placed the church on "
            "its Endangered Places list, and the local community has organized ongoing restoration "
            "efforts to stabilize and eventually rehabilitate the structure as a community center."
        ),
        "source": "AURIK",
        "confidence": 0.85,
    },
    {
        "name": "Milk River Valley Church (Kremlin-Gildford Church of the Brethren)",
        "type": "abandoned_church",
        "latitude": 48.67872,
        "longitude": -110.22611,
        "description": (
            "The Kremlin-Gildford Church of the Brethren — commonly known as the Milk River Valley "
            "Church — was built beginning in 1915 and completed around 1918 on the remote windswept "
            "plains of Hill County, Montana, between the small Hi-Line communities of Kremlin and "
            "Gildford, constructed by German-Russian immigrant farmers who brought the Church of "
            "the Brethren tradition from the Great Plains settlements to Montana's homestead "
            "frontier. Severe drought, economic hardship, and the collapse of wheat prices following "
            "World War I devastated the congregation within a generation, and the church closed as "
            "families abandoned their claims and left the land. The white clapboard church and an "
            "adjacent parsonage now stand in isolation on a dirt track miles from any paved road, "
            "surrounded by fields that return annually to wheat but contain no remaining community, "
            "embodying the melancholy of the failed Hi-Line homestead era. Photographers and rural "
            "heritage enthusiasts seek out the site for its dramatic prairie isolation and its "
            "intact but deteriorating exterior, which has been documented by several Great Plains "
            "photography projects."
        ),
        "source": "AURIK",
        "confidence": 0.85,
    },
    {
        "name": "Capilla de San Juan Bautista (La Garita)",
        "type": "abandoned_church",
        "latitude": 37.84662,
        "longitude": -106.26054,
        "description": (
            "The Capilla de San Juan Bautista in La Garita, Saguache County, Colorado, is a "
            "Territorial Adobe-style church built in 1879 and rebuilt in 1926 after an earlier "
            "structure burned, featuring thick stuccoed adobe walls, a Gothic Revival bell tower, "
            "and a prominent presence in the valley settled by Hispano Catholic families who moved "
            "northward from the Conejos River settlements. The chapel served as an active parish "
            "center until 1895 and thereafter as a mission church until it was abandoned in the "
            "1960s after the surrounding community's population dwindled; the adjacent Casa de Cura "
            "(priest's residence) fell into ruin and has been preserved as a roofless adobe shell. "
            "The site was partially restored in the 2000s as the San Juan Catholic Spiritual "
            "Center, though the original convent ruins and cemetery remain in their historic "
            "deteriorated state as the most evocative elements of the complex. The ruins of the "
            "Casa de Cura, set against the backdrop of the San Juan Mountains, draw photographers "
            "and religious pilgrims exploring the Sangre de Cristo National Heritage Area."
        ),
        "source": "AURIK",
        "confidence": 0.75,
    },
    {
        "name": "Espinosa Church",
        "type": "abandoned_church",
        "latitude": 37.21,
        "longitude": -105.44,
        "description": (
            "The Espinosa Church is a derelict historic Catholic chapel in the small unincorporated "
            "community of Espinosa in Costilla County, Colorado, part of the network of small "
            "Hispano Catholic mission churches that served the scattered farming and ranching "
            "settlements of the San Luis Valley established by New Mexican settlers in the "
            "mid-nineteenth century. Like many rural mission chapels of the region, the Espinosa "
            "church was a simple adobe or stone vernacular structure that served as the spiritual "
            "and social center of a hamlet-scale community dependent on subsistence farming and "
            "stock grazing. Population decline and road improvements that made travel to larger "
            "parish centers feasible led to the church's abandonment in the mid-to-late twentieth "
            "century, leaving the structure to gradually deteriorate under seasonal freeze-thaw "
            "cycles and deferred maintenance. The church is documented in urban exploration and "
            "heritage photography collections focusing on the San Luis Valley's distinctive "
            "network of abandoned Hispano mission architecture."
        ),
        "source": "AURIK",
        "confidence": 0.65,
    },
    {
        "name": "Jaroso Church (Sacred Heart Church)",
        "type": "abandoned_church",
        "latitude": 37.003,
        "longitude": -105.625,
        "description": (
            "The Sacred Heart Church (Sagrado Corazon de Jesus) in Jaroso, Costilla County, "
            "Colorado, is an abandoned Catholic chapel that served the small railroad settlement "
            "of Jaroso, founded in the late nineteenth century along a branch line of the Denver "
            "and Rio Grande Railroad that briefly brought commercial activity to this high-altitude "
            "San Luis Valley community before the line's abandonment left the town isolated. The "
            "modest adobe and frame structure was the religious center for Jaroso's largely "
            "Hispanic Catholic population, which sustained itself through small-scale ranching and "
            "farming in the shallow valley below the Sangre de Cristo Mountains. As the railroad "
            "economy collapsed and younger generations moved to larger regional centers, Jaroso's "
            "population contracted to a handful of households, and the church fell into disuse "
            "and gradual structural deterioration. The abandoned church and a few surviving "
            "residences make Jaroso one of the most evocative near-ghost settlements in the San "
            "Luis Valley, photographed for its dramatic mountain backdrop and preserved vernacular "
            "architecture."
        ),
        "source": "AURIK",
        "confidence": 0.75,
    },
    {
        "name": "Cathedral High School and Convent (Denver)",
        "type": "abandoned_church",
        "latitude": 39.7456,
        "longitude": -104.9849,
        "description": (
            "The Cathedral High School and Convent at 1840 Grant Street in Denver's Uptown "
            "neighborhood was completed in 1921 in a Spanish Renaissance Revival style designed "
            "by architect Harry J. Manning, built to house a Catholic girls' school and a Sisters "
            "of Charity convent complex that operated under the Archdiocese of Denver for decades "
            "and later became nationally known as Seton House, a facility providing charitable "
            "social services including AIDS hospice care during the 1980s and 1990s epidemic. "
            "The five-story brick and terra cotta building features an ornate Spanish Revival "
            "facade with decorative pilasters, arched window surrounds, and a prominent cornice, "
            "representing one of the most architecturally elaborate institutional buildings of "
            "its era in Denver. The property was sold and has changed hands multiple times since "
            "Seton House closed, with redevelopment plans repeatedly stalling amid financial and "
            "legal disputes, leaving the historic structure classified by the City of Denver as a "
            "Neglected and Derelict Building subject to ongoing fines and enforcement actions. "
            "The deteriorating complex has suffered extensive vandalism and structural neglect, "
            "attracting urban explorers and preservation advocates who document its continuing "
            "decay while campaigning for stabilization and adaptive reuse."
        ),
        "source": "AURIK",
        "confidence": 0.85,
    },
    {
        "name": "Modoc Mission Church (Wyandotte)",
        "type": "abandoned_church",
        "latitude": 36.804,
        "longitude": -94.6952,
        "description": (
            "The Modoc Mission Church near Wyandotte in Ottawa County, Oklahoma, was established to "
            "serve the Modoc tribe who were forcibly relocated to Indian Territory following the "
            "Modoc War of 1872–73 in California, making it a poignant symbol of the cultural "
            "resilience of a people who endured forced removal from their homeland in the Klamath "
            "Basin. The mission church served as a spiritual anchor for the small Modoc community "
            "within the broader mosaic of relocated tribes in the old Quapaw Agency region of "
            "northeastern Oklahoma, offering worship and community gatherings in a vernacular frame "
            "building typical of late nineteenth-century mission architecture. As the Modoc "
            "population remained small and geographically dispersed, the congregation dwindled over "
            "the twentieth century and the building fell into disuse, leaving it as a weathered "
            "historic remnant in Ottawa County. The church is documented by heritage organizations "
            "as one of the few physical traces of the relocated Modoc community in northeastern "
            "Oklahoma."
        ),
        "source": "AURIK",
        "confidence": 0.65,
    },
    {
        "name": "Second Presbyterian Church (Tulsa)",
        "type": "abandoned_church",
        "latitude": 36.1515,
        "longitude": -95.9635,
        "description": (
            "The Second Presbyterian Church of Tulsa, Oklahoma, was organized in 1917 as a "
            "congregation spun off from the rapidly growing First Presbyterian Church, establishing "
            "its 'White Church' at the corner of Zunis Avenue and Barton Street on October 21, 1917, "
            "in a white-painted wood-frame and stucco structure that became a modest landmark in the "
            "surrounding residential neighborhood. The congregation flourished through the oil-boom "
            "decades of the 1920s and 1930s, serving a working-class and middle-class Presbyterian "
            "community in south Tulsa, but declined as the neighborhood demographics shifted "
            "following construction of the Crosstown Expressway and mid-century suburban migration. "
            "The church was reportedly abandoned by 2019 and the building has since drawn attention "
            "from preservation advocates and urban explorers who document its deteriorating but "
            "still-standing form in a changing section of Tulsa. Architectural and community "
            "documentation is maintained by the Abandoned Atlas Foundation and Abandoned Oklahoma."
        ),
        "source": "AURIK",
        "confidence": 0.75,
    },
    {
        "name": "Earlsboro Church of Christ",
        "type": "abandoned_church",
        "latitude": 35.3281,
        "longitude": -96.8014,
        "description": (
            "The Earlsboro Church of Christ is a two-story buff-brick building with a bell tower and "
            "parapeted gable roof constructed in 1929 in Earlsboro, Pottawatomie County, Oklahoma, "
            "under the leadership of local resident J.A. Ingram at a cost of approximately $25,000 — "
            "a remarkable investment for a small town that had boomed during the oil era and earlier "
            "as a frontier whisky town on the edge of Indian Territory. The auditorium could seat "
            "500 worshippers and the building included Sunday school rooms, a kitchen, and a "
            "basement, quickly becoming the social and spiritual center of Earlsboro's community. "
            "Attendance declined through the latter twentieth century as rural depopulation eroded "
            "the congregation, and the church was formally closed by the late 1990s or early 2000s; "
            "former members salvaged pews, pulpit chairs, and a communion tray, while the "
            "stained-glass windows were removed for safekeeping in the 2010s. The weathered shell "
            "now stands as an atmospheric ruin frequently photographed by urban explorers and "
            "featured on Only In Your State as one of Oklahoma's most evocative abandoned religious "
            "sites."
        ),
        "source": "AURIK",
        "confidence": 0.85,
    },
    {
        "name": "Okfuskee Sunday School",
        "type": "abandoned_church",
        "latitude": 35.4441,
        "longitude": -96.2745,
        "description": (
            "The Okfuskee Sunday School is an abandoned rural church and community meeting hall in "
            "Okfuskee County, central Oklahoma, used through the 1950s when records indicate only a "
            "handful of regular worshippers attending, making it a vivid time capsule of the "
            "declining small rural congregation phenomenon that swept across the Oklahoma plains as "
            "agricultural mechanization and rural depopulation accelerated after World War II. The "
            "interior was found largely intact by explorers decades after closure, with original "
            "attendance boards, the pulpit, an offering plate, and a flooded basement containing "
            "artifacts including old trophies and a vintage refrigerator, suggesting that the "
            "community used the building for secular as well as religious purposes. The building is "
            "part of the larger pattern of Okfuskee County's abandoned structures rooted in the "
            "post-Depression rural exodus and the decline of once-thriving agricultural hamlets. "
            "Abandoned Oklahoma and the Abandoned Atlas Foundation have documented the site "
            "extensively in photography and video."
        ),
        "source": "AURIK",
        "confidence": 0.65,
    },
    {
        "name": "Cache Creek Mission (Apache)",
        "type": "abandoned_church",
        "latitude": 34.8955,
        "longitude": -98.3634,
        "description": (
            "The Cache Creek Mission near Apache in Caddo County, southwestern Oklahoma, was one of "
            "the early Baptist mission stations established for the Kiowa, Comanche, and Apache "
            "tribes of the southern Plains following their confinement to the reservation created by "
            "the Medicine Lodge Treaty of 1867, serving both as a house of worship and a community "
            "outreach center in an era when federal Indian policy promoted Christianization "
            "alongside land allotment. The mission stood near Cache Creek, a tributary of the "
            "Washita River in the former Kiowa-Comanche-Apache Reservation lands, in a landscape "
            "that saw profound disruption as the reservation was broken up under the Dawes Act "
            "allotments of the early twentieth century. As the surrounding Caddo County developed "
            "into an agricultural district and Native American congregants dispersed, the original "
            "mission church fell into disuse and gradual structural deterioration. The site "
            "represents the complex religious history of the southern Plains missions and their role "
            "in the cultural transitions of the late nineteenth and early twentieth centuries."
        ),
        "source": "AURIK",
        "confidence": 0.65,
    },
    {
        "name": "First Baptist Church of Clearview",
        "type": "abandoned_church",
        "latitude": 35.3986,
        "longitude": -96.1875,
        "description": (
            "The First Baptist Church of Clearview served the historic all-Black town of Clearview "
            "in Okfuskee County, Oklahoma, one of more than fifty African-American townships "
            "established in Oklahoma Territory and Indian Territory before statehood, founded in "
            "1903 by freedmen seeking self-determination, economic independence, and freedom from "
            "the racial violence and Jim Crow oppression prevalent elsewhere in the "
            "post-Reconstruction South. The church was the primary spiritual institution for "
            "Clearview's community of Black entrepreneurs, farmers, and educators who built a town "
            "complete with a hotel, brick school, print shop, and two churches served by the Fort "
            "Smith and Western Railroad. As the Great Depression decimated cotton prices and rural "
            "depopulation accelerated through the mid-twentieth century, Clearview's population "
            "collapsed from its peak and historic structures including the church building were lost "
            "to demolition or deterioration. Clearview survives with a tiny population (41 in 2020) "
            "as a recognized symbol of Black entrepreneurship and resilience, with the Oklahoma "
            "African American Educators Hall of Fame located there."
        ),
        "source": "AURIK",
        "confidence": 0.65,
    },
    {
        "name": "First Methodist Church (Sparks, OK)",
        "type": "abandoned_church",
        "latitude": 35.6114,
        "longitude": -96.8189,
        "description": (
            "The First Methodist Church in Sparks, Lincoln County, Oklahoma, served the railroad hub "
            "community that grew at the junction of the Eastern Oklahoma Railway and the Fort Smith "
            "and Western Railroad from 1902, when Sparks rapidly developed with over fifty "
            "businesses, banks, newspapers, schools, and several churches drawing settlers to land "
            "opened following the 1891 Sac and Fox Reservation land run. The town's population "
            "peaked at 503 in 1907 before entering a long decline driven by falling farm prices "
            "after World War I, the Great Depression, closure of the railroad in 1939, and "
            "shuttering of the schools by the 1990s, reducing Sparks to a near-ghost community of "
            "only 122 residents by 2020. The Methodist church building and other surviving "
            "structures — including the Masonic lodge and Farmers and Merchants Bank — now stand as "
            "relics in a community that still has a few inhabited homes and a post office. Abandoned "
            "Oklahoma has documented Sparks's surviving and abandoned structures as a case study of "
            "the vanishing Oklahoma railroad town."
        ),
        "source": "AURIK",
        "confidence": 0.65,
    },
    {
        "name": "Prairie Grove School/Church (Stratford)",
        "type": "abandoned_church",
        "latitude": 34.7953,
        "longitude": -96.9603,
        "description": (
            "The Prairie Grove School was constructed in 1938 as a Works Progress Administration "
            "project west of Stratford in Garvin County, Oklahoma, at a cost of $5,300 from WPA "
            "funds plus $2,563 in local contributions, built with a stage, moveable partition, water "
            "fountain, and a basketball court as a multi-purpose community facility for the rural "
            "farm families of the Prairie Grove area. The school consolidated with Stratford public "
            "schools in 1953 due to declining enrollment, and the building was repurposed as the "
            "Prairie Grove Church, serving a small congregation as a community hub for another two "
            "decades until attendance fell away in the early 1970s. Since abandonment the building "
            "has deteriorated severely over five decades of Oklahoma weather and deferred "
            "maintenance, now reduced to a partially collapsed ruin described by preservationists as "
            "a characteristic but rapidly disappearing example of Depression-era WPA vernacular "
            "construction in rural Oklahoma. The Abandoned Oklahoma and Abandoned Atlas Foundation "
            "websites have documented its ongoing decay."
        ),
        "source": "AURIK",
        "confidence": 0.65,
    },
    {
        "name": "Eden Baptist Church (Hennessey)",
        "type": "abandoned_church",
        "latitude": 36.1782,
        "longitude": -97.8488,
        "description": (
            "Eden Baptist Church northeast of Hennessey in Kingfisher County, Oklahoma, was "
            "dedicated on September 16, 1928, when a modern brick building replaced the original "
            "1917 frame church and the congregation renamed it from Valley Center Baptist to Eden "
            "Baptist, quickly earning the nickname 'The City Church in the Country' for its "
            "impressive auditorium, basement rooms, kitchen, and notable steeple topped with an "
            "angel statue. The brick structure represented the prosperity of the surrounding "
            "wheat-farming community in the 1920s, but the Dust Bowl and Great Depression devastated "
            "the agricultural economy, and as rural populations declined through the mid-century the "
            "congregation shrank until the church closed on September 30, 1973, after which the "
            "property was transferred to the Hennessey First Baptist Church. The angel statue was "
            "stolen from the steeple in the 1990s, and subsequent storms collapsed the north wall "
            "and destroyed the steeple, leaving the brick shell standing in the prairie as a "
            "poignant monument to the rise and fall of the Oklahoma farming frontier."
        ),
        "source": "AURIK",
        "confidence": 0.75,
    },
    {
        "name": "Saddle Mountain Mission (Cache)",
        "type": "abandoned_church",
        "latitude": 34.6359,
        "longitude": -98.562,
        "description": (
            "The Saddle Mountain Mission was founded in 1903 near Mountain View in Kiowa County, "
            "Oklahoma, by Isabel Crawford, a Canadian Baptist missionary who communicated with her "
            "Kiowa congregation partly through Plains Indian Sign Language due to her near-deafness, "
            "making the mission notable for pioneering a model of native Christian leadership that "
            "allowed non-ordained, non-White ministers elected directly by the congregation — a "
            "radical departure from the paternalistic norm of the era. The mission served as a "
            "center of independent Kiowa and Comanche Christian identity for six decades, producing "
            "numerous native missionaries and pastors and maintaining a cemetery that remains active "
            "with descendants of the original congregation. Internal disputes about church "
            "governance led to the mission's closure in the early 1960s, and in 1963 the original "
            "church building was physically relocated approximately 30 miles south to Eagle Park "
            "near Cache, Oklahoma, where it stands abandoned and deteriorating in the former "
            "amusement park grounds. The Saddle Mountain Mission is listed on Preservation "
            "Oklahoma's Most Endangered Places and is recognized as a significant site in the "
            "history of Native American Christianity."
        ),
        "source": "AURIK",
        "confidence": 0.75,
    },
    {
        "name": "Bradford Christian School and Pryor Christian Center",
        "type": "abandoned_church",
        "latitude": 36.3084,
        "longitude": -95.3169,
        "description": (
            "Bradford Christian School and the Pryor Christian Center operated as a combined church "
            "and private school campus in Pryor, Mayes County, Oklahoma, founded in 1987 by John and "
            "Brenda Alley within the Pryor Christian Center building, serving the evangelical "
            "community of northeastern Oklahoma with both religious services and K-12 Christian "
            "education until the school separated and relocated to a new site in 2000. The remaining "
            "building continued as the Pryor Christian Center until the congregation dissolved and "
            "the property was abandoned, with the building later suffering a fire that resulted in "
            "significant structural damage before it was eventually demolished. The site represents "
            "the pattern of independent evangelical church-school campuses that proliferated in "
            "Oklahoma's small cities during the 1980s religious revival and subsequently declined "
            "with congregation splits and economic pressures. Abandoned Oklahoma documented the "
            "building's deteriorated state before its eventual demolition."
        ),
        "source": "AURIK",
        "confidence": 0.65,
    },
    {
        "name": "Victory Baptist Church (Pershing)",
        "type": "abandoned_church",
        "latitude": 36.5933,
        "longitude": -96.2753,
        "description": (
            "Victory Baptist Church in Pershing, Osage County, northern Oklahoma, is a "
            "stone-construction church building estimated to have been built in the early to "
            "mid-1920s, with records from 1924 showing approximately sixty attendees drawn from "
            "nearby communities including Pawhuska and Nelogoney under Pastor Nail, followed by Rev. "
            "James Gore in 1934. The congregation remained active through the rural prosperity of "
            "the 1920s and the hardship of the Depression and Dust Bowl years, but declining "
            "membership and a failing roof that was never repaired led to the church's closure "
            "during the 1960s, after which the building stood abandoned and roofless. The adjacent "
            "stone parsonage, constructed from the same local stone as the church, appears to have "
            "continued as a residence or storage structure, surviving in better condition than the "
            "church itself. The abandoned shell has been documented by Abandoned Oklahoma as an "
            "iconic rural relic in the rolling hills of Osage County."
        ),
        "source": "AURIK",
        "confidence": 0.75,
    },
    {
        "name": "First Methodist Church, Jermyn, Texas",
        "type": "abandoned_church",
        "latitude": 33.2618,
        "longitude": -98.3919,
        "description": (
            "Erected in 1909 as the first church in the small Jack County ranching town of Jermyn, "
            "this Methodist Episcopal building was designated a Recorded Texas Historic Landmark in "
            "1968. As Jermyn's population shrank from its early-20th-century peak, the congregation "
            "dissolved and the church was quietly abandoned. Original furnishings reportedly remain "
            "inside the weathered frame structure."
        ),
        "source": "AURIK",
        "confidence": 0.85,
    },
    {
        "name": "St. Barbara's Catholic Church Ruins, Thurber, Texas",
        "type": "abandoned_church",
        "latitude": 32.487,
        "longitude": -98.421,
        "description": (
            "Built in 1897 to serve the predominantly Italian and Polish Catholic coal miners of "
            "Erath County's company town of Thurber, which at its peak housed nearly 10,000 "
            "residents. When the Texas & Pacific Coal Company converted operations to oil and "
            "relocated its workforce in 1921, Thurber was emptied within months; demolition crews "
            "left the church standing out of reverence. Only brick ruins and a museum chimney mark "
            "the site today."
        ),
        "source": "AURIK",
        "confidence": 0.75,
    },
    {
        "name": "Mound Prairie Lutheran Church, Alto, Texas",
        "type": "abandoned_church",
        "latitude": 31.671,
        "longitude": -95.08,
        "description": (
            "Founded in 1854 by Swedish immigrants in Cherokee County, this is one of the oldest "
            "Lutheran congregations in Texas, established by settlers who came with the Swedish "
            "emigration movement led by Gustaf Unonius. The rural community shrank as agriculture "
            "mechanized and younger generations relocated to cities, leaving the church largely "
            "dormant. The historic building is periodically preserved by the Texas Swedish "
            "descendants organization."
        ),
        "source": "AURIK",
        "confidence": 0.75,
    },
    {
        "name": "Monument United Methodist Church, Monument, Kansas",
        "type": "abandoned_church",
        "latitude": 39.1044,
        "longitude": -101.0072,
        "description": (
            "A striking 1930 Tudor Revival brick church built by the residents of this Logan County "
            "ghost town that had once been a Butterfield Overland Despatch relay station on the "
            "Smoky Hill Trail. As western Kansas depopulated through the mid-20th century, "
            "attendance collapsed and the doors closed for good in 1966; pews were redistributed to "
            "churches in neighboring towns. The roof has since caved in and the interior bears "
            "graffiti, but the exterior walls still stand on the wind-swept prairie."
        ),
        "source": "AURIK",
        "confidence": 0.85,
    },
    {
        "name": "Walnut Valley Presbyterian Church, Cowley County, Kansas",
        "type": "abandoned_church",
        "latitude": 37.24,
        "longitude": -96.88,
        "description": (
            "Organized in 1879 along the former Winfield–Eldorado stage route in Cowley County, this "
            "rural Presbyterian congregation built a modest wooden church that was destroyed by "
            "lightning and rebuilt in 1915. Declining farm populations through the mid-20th century "
            "rendered the congregation unsustainable, and it formally merged with another church in "
            "1971. The empty building subsequently served as a farm outbuilding before being "
            "abandoned."
        ),
        "source": "AURIK",
        "confidence": 0.65,
    },
    {
        "name": "Nicodemus First Baptist Church, Nicodemus, Kansas",
        "type": "abandoned_church",
        "latitude": 39.393,
        "longitude": -99.617,
        "description": (
            "Founded in 1877 by freed slaves from Kentucky who established the only remaining "
            "all-Black frontier town on the Great Plains in Graham County, this Baptist congregation "
            "was the spiritual anchor of Nicodemus from its earliest days. The town's population "
            "plummeted after the railroad bypassed it in 1888; by the 20th century only a handful of "
            "families remained. The original church building is preserved within the Nicodemus "
            "National Historic Site."
        ),
        "source": "AURIK",
        "confidence": 0.85,
    },
    {
        "name": "Bloodland Methodist Church, Pulaski County, Missouri",
        "type": "abandoned_church",
        "latitude": 37.687,
        "longitude": -92.152,
        "description": (
            "A Methodist congregation in a German-American farming village of Pulaski County that "
            "had grown to roughly 100 residents and three churches by 1900. In 1940 the U.S. Army "
            "condemned the entire community to build Fort Leonard Wood, forcibly relocating all "
            "families within weeks; church buildings were dismantled or demolished. Only the "
            "adjacent Bloodland Cemetery survives inside the military reservation as a monument to "
            "the lost community."
        ),
        "source": "AURIK",
        "confidence": 0.75,
    },
    {
        "name": "Windyville Methodist Church, Windyville, Missouri",
        "type": "abandoned_church",
        "latitude": 37.707,
        "longitude": -92.924,
        "description": (
            "A small Methodist church built around 1880 in this remote Dallas County hamlet, once a "
            "quiet crossroads farming settlement in the Ozark hills. Rural exodus through the 20th "
            "century reduced Windyville to one of Missouri's most isolated ghost towns; the church "
            "closed as its congregation dispersed to larger towns. The abandoned building is "
            "periodically featured in Missouri ghost-town photography projects."
        ),
        "source": "AURIK",
        "confidence": 0.65,
    },
    {
        "name": "Rodney Presbyterian Church, Rodney, Mississippi",
        "type": "abandoned_church",
        "latitude": 31.863,
        "longitude": -91.197,
        "description": (
            "Chartered by the Mississippi Legislature in 1828 and built between 1829–1832 in Federal "
            "style, this brick Presbyterian church served what was once a thriving Mississippi River "
            "port that nearly became the state capital by a margin of three votes. Fires, yellow "
            "fever, Civil War skirmishes (a cannonball hole remains above one window), and the "
            "river's course change collectively destroyed the town; the congregation shrank to 16 "
            "members by 1923. It is now a preserved ghost-town landmark maintained by the Rodney "
            "History and Preservation Society."
        ),
        "source": "AURIK",
        "confidence": 0.85,
    },
    {
        "name": "Old Providence Presbyterian Church, Church Hill, Mississippi",
        "type": "abandoned_church",
        "latitude": 31.821,
        "longitude": -91.096,
        "description": (
            "A Greek Revival brick church built in 1829 in Jefferson County near Natchez, founded by "
            "Scots-Irish Presbyterian planters in what was then a prosperous antebellum community. "
            "Civil War disruptions and postwar economic collapse gutted the congregation, and Church "
            "Hill itself faded to a near-ghost town with only a handful of residents. The building "
            "is rarely used and stands as a testament to the antebellum religious landscape of the "
            "Natchez Trace corridor."
        ),
        "source": "AURIK",
        "confidence": 0.75,
    },
    {
        "name": "Centennial Baptist Church, Helena, Arkansas",
        "type": "abandoned_church",
        "latitude": 34.525,
        "longitude": -90.591,
        "description": (
            "Founded in 1865 and housed in a 1905 brick building designed by African American "
            "architect Henry James Price, this Baptist church in Phillips County was a cornerstone "
            "of Helena's Black community during the Jim Crow era. Designated a National Historic "
            "Landmark for its architectural and cultural significance, the congregation held its "
            "last formal services in 1998 as membership dwindled. A 2020 tornado caused severe "
            "structural damage, and the building now stands in fragile ruin."
        ),
        "source": "AURIK",
        "confidence": 0.85,
    },
    {
        "name": "Cades Cove Primitive Baptist Church, Blount County, Tennessee",
        "type": "abandoned_church",
        "latitude": 35.6,
        "longitude": -83.843,
        "description": (
            "Organized in 1827 as the oldest congregation in Cades Cove, this Primitive Baptist "
            "church built its original log structure that same year to serve the isolated Great "
            "Smoky Mountains farming valley. The congregation held its last formal service in 1915 "
            "as younger generations left the cove, and the National Park Service acquired the land "
            "in the 1940s. The preserved white-frame building and adjacent cemetery are among the "
            "most visited historic structures in Great Smoky Mountains National Park."
        ),
        "source": "AURIK",
        "confidence": 0.85,
    },
    {
        "name": "Cades Cove Methodist Church, Blount County, Tennessee",
        "type": "abandoned_church",
        "latitude": 35.614,
        "longitude": -83.834,
        "description": (
            "The Methodist Episcopal, South congregation of Cades Cove traced its origins to 1827 "
            "and erected its simple white frame meeting house in 1902 to replace earlier structures "
            "in the remote Tennessee mountain valley. NPS acquisition of the Cades Cove area in the "
            "1940s ended active congregational use, though the building was carefully preserved. It "
            "stands today as a restored historic structure with no active congregation, open to park "
            "visitors year-round."
        ),
        "source": "AURIK",
        "confidence": 0.85,
    },
    {
        "name": "Rocky Valley Lutheran Church, Dooley, Montana",
        "type": "abandoned_church",
        "latitude": 48.882,
        "longitude": -104.389,
        "description": (
            "Built in 1915 by Norwegian Lutheran homesteaders on the remote Montana Hi-Line in "
            "Sheridan County, this prairie church served the scattered farming families who "
            "dry-farmed the windswept benchlands east of Wolf Point. Congregation numbers fell "
            "sharply after World War II as small farms consolidated and young people moved away, "
            "leaving the church unused for decades. A powerful windstorm in 2019 collapsed the "
            "structure, leaving only foundation remnants and the adjacent cemetery."
        ),
        "source": "AURIK",
        "confidence": 0.85,
    },
    {
        "name": "Bannack Methodist-Episcopal Church, Bannack, Montana",
        "type": "abandoned_church",
        "latitude": 45.165,
        "longitude": -113.001,
        "description": (
            "Erected in 1877 in Montana's first territorial capital in Beaverhead County, this "
            "church also housed a Masonic hall on its upper floor, reflecting the dual social "
            "functions of frontier religious buildings. Bannack's placer gold mines were largely "
            "exhausted by the 1870s and the town steadily emptied through the early 20th century. "
            "The church is now a preserved structure in Bannack State Park, a Montana ghost town on "
            "the National Register of Historic Places."
        ),
        "source": "AURIK",
        "confidence": 0.85,
    },
    {
        "name": "Garnet Mining Camp Chapel, Garnet, Montana",
        "type": "abandoned_church",
        "latitude": 46.769,
        "longitude": -113.432,
        "description": (
            "A non-denominational community chapel in one of Montana's largest intact ghost towns, "
            "located in Granite County east of Missoula at nearly 6,000 feet elevation. Gold mining "
            "in Garnet peaked in the 1890s, with a brief revival in the 1930s, before the camp was "
            "finally abandoned and partially destroyed by fire in 1947. The chapel and approximately "
            "30 other structures are maintained by the Bureau of Land Management as an open-air "
            "heritage site."
        ),
        "source": "AURIK",
        "confidence": 0.65,
    },
    {
        "name": "Norway Lutheran Church and Cemetery, Denbigh, North Dakota",
        "type": "abandoned_church",
        "latitude": 48.181,
        "longitude": -100.615,
        "description": (
            "Organized in 1884 at the Erick Espeseth farm by Norwegian immigrants in McHenry County, "
            "this congregation built its distinctive yellowish 'Denbigh Brick' Late Gothic Revival "
            "church in 1907, topped by a 65-foot bell tower visible for miles across the Mouse River "
            "valley. Declining rural populations eroded membership through the mid-20th century "
            "until the congregation dissolved. Listed on the National Register of Historic Places in "
            "1994, the church and cemetery remain important genealogical sites for "
            "Norwegian-American descendants."
        ),
        "source": "AURIK",
        "confidence": 0.85,
    },
    {
        "name": "Wolf Butte Lutheran Church, Adams County, North Dakota",
        "type": "abandoned_church",
        "latitude": 46.1,
        "longitude": -102.5,
        "description": (
            "A rural Norwegian Lutheran church built around 1910 in remote Adams County, 45 miles "
            "south of Dickinson, serving the scattered homesteading families who settled the "
            "southwestern North Dakota grasslands. Regular services ended in 1988 as the surrounding "
            "farm population dwindled to just a handful of families. The white frame church stands "
            "alone on open rangeland and has been documented by regional photography projects "
            "focused on vanishing prairie religious architecture."
        ),
        "source": "AURIK",
        "confidence": 0.65,
    },
    {
        "name": "Cottonwood Prairie Church, Cottonwood, South Dakota",
        "type": "abandoned_church",
        "latitude": 43.993,
        "longitude": -102.03,
        "description": (
            "A simple wooden prairie church in the ghost town of Cottonwood, Jackson County, "
            "sequentially used by Presbyterian (1915), Lutheran (1922), and Catholic (1928) "
            "congregations as was common in frontier communities that could not support separate "
            "denominational buildings. The post office closed in 1925 and the community faded as "
            "ranching consolidated; the church was last regularly used by the mid-20th century. It "
            "stands today as an icon of the Great Plains landscape, often photographed by travelers "
            "near Badlands National Park."
        ),
        "source": "AURIK",
        "confidence": 0.75,
    },
    {
        "name": "Okaton Community Church, Okaton, South Dakota",
        "type": "abandoned_church",
        "latitude": 43.997,
        "longitude": -100.955,
        "description": (
            "A wooden prairie church built around 1910 in Jones County's Okaton, one of the smallest "
            "incorporated municipalities in the United States with a population under 50. The "
            "community church served multiple homesteading families in an area where extreme drought "
            "and economic hardship drove most settlers away during the Dust Bowl era. The building "
            "stands largely abandoned on the open prairie, occasionally featured in studies of Great "
            "Plains ghost towns."
        ),
        "source": "AURIK",
        "confidence": 0.75,
    },
    {
        "name": "Zion Lutheran Church, Shelly, Minnesota",
        "type": "abandoned_church",
        "latitude": 47.456,
        "longitude": -96.791,
        "description": (
            "Founded in 1880 by Norwegian immigrants in Norman County's Red River Valley and built "
            "in 1883 in a Victorian Gothic style by the congregation of Elder Peder Efteland, this "
            "church survived being shifted off its foundation by a tornado in 1902. Rural "
            "depopulation and consolidation of surrounding farms steadily reduced the congregation, "
            "which eventually dissolved. Listed on the National Register of Historic Places in 1999, "
            "the church is maintained as a local heritage landmark."
        ),
        "source": "AURIK",
        "confidence": 0.85,
    },
    {
        "name": "Trondhjem Norwegian Lutheran Church, Lonsdale, Minnesota",
        "type": "abandoned_church",
        "latitude": 44.481,
        "longitude": -93.424,
        "description": (
            "Named for Trondheim, Norway, this congregation was established in 1877 by Norwegian "
            "immigrant farmers in Rice County and built its present church building in 1899 to "
            "replace an earlier structure. As rural consolidation and the shift away from "
            "Norwegian-language worship eroded membership, the congregation merged with a "
            "neighboring church, and the building passed into the care of a local historical "
            "preservation society. The structure is maintained as a cultural landmark and is "
            "occasionally open for heritage events."
        ),
        "source": "AURIK",
        "confidence": 0.75,
    },
    {
        "name": "Rock Valle Lutheran Church, Echo, Minnesota",
        "type": "abandoned_church",
        "latitude": 44.619,
        "longitude": -96.027,
        "description": (
            "Dedicated in May 1902 in Lyon County by Norwegian immigrant farming families, this "
            "rural Lutheran church took its name from the rocky valley terrain of the local "
            "landscape. Declining farm populations through the latter half of the 20th century left "
            "the congregation unable to sustain itself, and the church was closed and abandoned. The "
            "adjacent Rock Valle Cemetery contains graves dating to the 1890s settlement period."
        ),
        "source": "AURIK",
        "confidence": 0.65,
    },
    {
        "name": "St. Ambrose Church, St. Nazianz, Wisconsin",
        "type": "abandoned_church",
        "latitude": 43.999,
        "longitude": -87.926,
        "description": (
            "Built in 1898 in Gothic Revival style by the Salvatorian Fathers at their colony in "
            "Manitowoc County, this Catholic church formed the spiritual centerpiece of a community "
            "originally established in 1854 by the Reverend Ambrose Oschwald and German Catholic "
            "immigrants seeking a religious utopia. The Salvatorian seminary school that sustained "
            "the complex closed in 1982, and the church fell into disuse. The building has since "
            "been partially incorporated into a United Ministries campus while the original nave "
            "remains largely vacant."
        ),
        "source": "AURIK",
        "confidence": 0.85,
    },
    {
        "name": "Coon Prairie Lutheran Church, Vernon County, Wisconsin",
        "type": "abandoned_church",
        "latitude": 43.76,
        "longitude": -91.036,
        "description": (
            "Organized around 1862 by Norwegian Lutheran immigrants who settled the upland prairie "
            "of Vernon County along the Coon River valley, this congregation built a modest wooden "
            "church to serve the farming community in their native tradition. Rural out-migration "
            "through the 20th century gradually depleted the congregation until services became "
            "infrequent and eventually ceased. The white-frame church and nearby cemetery are "
            "maintained by Norwegian-American descendants as a heritage site."
        ),
        "source": "AURIK",
        "confidence": 0.65,
    },
    {
        "name": "Central Mine Methodist Church, Central, Michigan",
        "type": "abandoned_church",
        "latitude": 47.407,
        "longitude": -88.204,
        "description": (
            "Built in 1868–1869 on the Keweenaw Peninsula by Cornish copper miners who brought their "
            "Methodist faith from Cornwall, England, this church served the community around the "
            "Central copper mine until the mine closed in 1898. The congregation officially "
            "disbanded in 1903 as the town's population departed, though annual reunion services "
            "held every July since 1907 have kept the building from true abandonment. Listed on the "
            "National Register as part of the Central Mine Historic District, the building retains "
            "its original handmade pews."
        ),
        "source": "AURIK",
        "confidence": 0.85,
    },
    {
        "name": "Martin Corners Methodist Church, Barry County, Michigan",
        "type": "abandoned_church",
        "latitude": 42.646,
        "longitude": -85.133,
        "description": (
            "A rural Methodist congregation established in 1888 at the crossroads community of "
            "Martin Corners, six miles east of Hastings in Barry County, serving the surrounding "
            "agricultural township. As farms consolidated and rural populations shifted toward "
            "larger towns, the congregation lost critical mass and was officially dissolved in 1972. "
            "The white frame building, situated alongside an abandoned one-room schoolhouse, "
            "deteriorates amid farmland."
        ),
        "source": "AURIK",
        "confidence": 0.75,
    },
    {
        "name": "Bethel Methodist Church, Crawford County, Indiana",
        "type": "abandoned_church",
        "latitude": 38.262,
        "longitude": -86.506,
        "description": (
            "A frontier Methodist congregation established in the 1820s in the hill country of "
            "Crawford County, one of Indiana's earliest organized churches serving the scattered "
            "pioneer farming communities along the Ohio River tributary valleys. As younger "
            "generations left for factory towns and the congregation dwindled, the church held its "
            "last services in the mid-20th century. The simple frame building has been abandoned "
            "amid the Hoosier National Forest."
        ),
        "source": "AURIK",
        "confidence": 0.65,
    },
    {
        "name": "Old Zion German Reformed Church, Columbiana County, Ohio",
        "type": "abandoned_church",
        "latitude": 40.872,
        "longitude": -80.752,
        "description": (
            "Founded around 1835 by German Reformed immigrants in rural Columbiana County along "
            "Ohio's eastern border, this congregation served Pennsylvania-German farming families in "
            "the rolling hills southwest of Youngstown. The congregation merged with a larger German "
            "Reformed church in the early 20th century, and the original brick building was "
            "subsequently abandoned. The structure stands today in weathered condition on private "
            "farmland."
        ),
        "source": "AURIK",
        "confidence": 0.65,
    },
    {
        "name": "Hauge Lutheran Church, Norway, Illinois",
        "type": "abandoned_church",
        "latitude": 41.465,
        "longitude": -88.666,
        "description": (
            "Built in 1847 in the Fox River Valley community of Norway, Kendall County, this church "
            "was the congregation of the first permanent Norwegian settlement in Illinois, founded "
            "by 'low church' Haugean Lutherans who rejected the Norwegian state church. After the "
            "congregation merged with another church in 1918, the building eventually became home to "
            "the Norsk Museum dedicated to Norwegian-American heritage. Listed on the National "
            "Register of Historic Places in 2016, it no longer functions as a house of worship."
        ),
        "source": "AURIK",
        "confidence": 0.85,
    },
    {
        "name": "St. John's United Church of Christ, Siegel, Iowa",
        "type": "abandoned_church",
        "latitude": 42.829,
        "longitude": -92.357,
        "description": (
            "Founded in 1874 by German Evangelical immigrants in Douglas Township, Bremer County, "
            "following a doctrinal split from a neighboring Lutheran congregation, this church is "
            "the sole surviving structure of the ghost town of Siegel, which had a post office from "
            "1889 to 1897. By the 1940s all other community buildings had vanished as agricultural "
            "consolidation emptied the landscape, leaving the church standing alone on Killdeer "
            "Avenue. A tiny membership of around 80 occasionally gathers there, making it a living "
            "relic of a vanished prairie town."
        ),
        "source": "AURIK",
        "confidence": 0.85,
    },
    {
        "name": "Buckhorn Church, Buckhorn, Iowa",
        "type": "abandoned_church",
        "latitude": 42.044,
        "longitude": -90.478,
        "description": (
            "Built in 1898 to serve the residents of Buckhorn, a small Jackson County farming "
            "community in northeastern Iowa, this community church hosted baptisms, Sunday School, "
            "and seasonal celebrations for area families. In the 1960s, the surrounding land was "
            "purchased for a large-scale dairy operation, and the remaining households relocated; "
            "the town was effectively erased. The white-frame church with its red metal roof still "
            "stands beside the old cemetery as the last visible trace of Buckhorn."
        ),
        "source": "AURIK",
        "confidence": 0.65,
    },
    {
        "name": "Pilgrim Holiness Church (Baled Hay Church), Arthur, Nebraska",
        "type": "abandoned_church",
        "latitude": 41.571,
        "longitude": -101.689,
        "description": (
            "Constructed in 1928 in the Nebraska Sandhills from baled rye straw — two-foot-thick "
            "walls plastered inside and stuccoed outside — because conventional building materials "
            "were prohibitively expensive in this treeless region, this Pilgrim Holiness church is "
            "believed to be the oldest baled-straw church in North America. Services ceased in the "
            "mid-1960s after membership in Arthur County's sparse population fell below a viable "
            "threshold. Preserved on the National Register of Historic Places since 1979, it is now "
            "maintained as a museum by the Arthur County Historical Society."
        ),
        "source": "AURIK",
        "confidence": 0.85,
    },
    {
        "name": "Steele City Methodist Church, Steele City, Nebraska",
        "type": "abandoned_church",
        "latitude": 40.043,
        "longitude": -97.003,
        "description": (
            "A Methodist congregation that flourished in this Jefferson County railroad town in the "
            "1880s, when Steele City briefly served as a regional agricultural hub along the Kansas "
            "City and Omaha Railway. The railroad's decline shifted commerce to nearby towns, and "
            "Steele City's population fell from several hundred to fewer than 50; the church was "
            "abandoned and the building left to the elements. The ghost town retains a few "
            "structures including the silent church."
        ),
        "source": "AURIK",
        "confidence": 0.65,
    },
    {
        "name": "South Pass City Methodist Church, South Pass City, Wyoming",
        "type": "abandoned_church",
        "latitude": 42.467,
        "longitude": -108.8,
        "description": (
            "Established in 1868 during the gold rush that briefly swelled South Pass City's "
            "population to nearly 4,000 in Fremont County, this Methodist congregation hosted "
            "circuit-riding preachers serving the South Pass mining district. Gold ore quality "
            "declined sharply by 1872 and the town was nearly deserted within a decade; the church "
            "closed shortly thereafter. Now a Wyoming State Historic Site, the building is preserved "
            "and interpreted for visitors as part of one of the state's best-documented ghost towns."
        ),
        "source": "AURIK",
        "confidence": 0.75,
    },
    {
        "name": "St. Aloysius Catholic Church Ruins, Morley, Colorado",
        "type": "abandoned_church",
        "latitude": 37.032,
        "longitude": -104.506,
        "description": (
            "Hand-built in 1917 by Italian, Slavic, and Mexican Catholic coal miners in the Colorado "
            "Fuel & Iron Company town of Morley, Las Animas County, which once housed over 600 "
            "residents at its peak in the 1920s. When CF&I closed the mine in 1956 and demolished "
            "the town, crews refused to raze the church out of reverence; it is the only structure "
            "left standing, visible from Interstate 25. Its Spanish colonial–influenced bell tower "
            "still rises above the ruins."
        ),
        "source": "AURIK",
        "confidence": 0.85,
    },
    {
        "name": "Animas Forks Community Church, San Juan County, Colorado",
        "type": "abandoned_church",
        "latitude": 37.921,
        "longitude": -107.572,
        "description": (
            "A non-denominational community church built around 1878 in the silver mining ghost town "
            "of Animas Forks, perched at 11,200 feet elevation in the San Juan Mountains where "
            "winters rendered the site uninhabitable for months each year. Silver prices collapsed "
            "in 1893, gutting the population, and the last permanent residents departed by the "
            "1920s. The structure is now in ruins alongside several other preserved buildings "
            "maintained by the Bureau of Land Management."
        ),
        "source": "AURIK",
        "confidence": 0.75,
    },
    {
        "name": "Grafton LDS Meetinghouse, Grafton, Utah",
        "type": "abandoned_church",
        "latitude": 37.167,
        "longitude": -113.08,
        "description": (
            "Built in 1886 to serve as both church and schoolhouse for this Church of Jesus Christ "
            "of Latter-day Saints pioneer settlement on the Virgin River in Washington County, the "
            "meetinghouse survived when periodic flooding and Black Hawk War raids of the 1860s "
            "drove settlers away and back repeatedly. The last residents departed by 1944 and the "
            "LDS branch was discontinued in 1921, leaving behind one of the most photographed ghost "
            "towns in the American West. The meetinghouse, pioneer homes, and cemetery are now "
            "preserved by the Grafton Heritage Partnership."
        ),
        "source": "AURIK",
        "confidence": 0.85,
    },
    {
        "name": "Chesterfield LDS Meetinghouse, Chesterfield, Idaho",
        "type": "abandoned_church",
        "latitude": 42.867,
        "longitude": -111.902,
        "description": (
            "Established in 1879 by Latter-day Saint pioneers in Bannock County as part of the 'Bear "
            "Lake Stake' colonization effort ordered by Brigham Young, the Chesterfield community "
            "built a Greek Revival-style meetinghouse that anchored the farming village for half a "
            "century. When the railroad bypassed Chesterfield and younger families departed for more "
            "connected communities, the town emptied by the late 1930s. It is now considered one of "
            "Idaho's best-preserved Mormon ghost towns and is listed on the National Register."
        ),
        "source": "AURIK",
        "confidence": 0.85,
    },
    {
        "name": "Our Lady of Tears Catholic Church, Silver City, Idaho",
        "type": "abandoned_church",
        "latitude": 43.023,
        "longitude": -116.733,
        "description": (
            "Built in 1898 to minister to the Catholic miners of the Owyhee Mountains' silver boom, "
            "this church served Silver City at its height when the remote Owyhee County community "
            "had 75 or more buildings and several thousand residents. As ore deposits thinned and "
            "the population contracted through the early 20th century, the church held increasingly "
            "infrequent services. Today Silver City is a preserved but sparsely occupied ghost town "
            "accessible by unpaved mountain road, with only a handful of seasonal residents; the "
            "church holds special masses occasionally."
        ),
        "source": "AURIK",
        "confidence": 0.75,
    },
    {
        "name": "Unionville Methodist Church, Unionville, Nevada",
        "type": "abandoned_church",
        "latitude": 40.446,
        "longitude": -118.122,
        "description": (
            "Founded around 1863 in a Pershing County silver mining camp that boasted 1,500 "
            "residents at its peak in the late 1860s, this Methodist congregation served miners from "
            "the Arizona Mine and surrounding claims in Buena Vista Canyon. The ore quality declined "
            "sharply by the 1870s, a fire in 1872 destroyed much of the town, and the county seat "
            "moved to Winnemucca in 1873, reducing Unionville to fewer than 30 residents. Church "
            "ruins are still visible in the canyon alongside Mark Twain's former cabin, now a "
            "bed-and-breakfast."
        ),
        "source": "AURIK",
        "confidence": 0.75,
    },
    {
        "name": "Rhyolite Community Church Ruins, Rhyolite, Nevada",
        "type": "abandoned_church",
        "latitude": 36.896,
        "longitude": -116.829,
        "description": (
            "A non-denominational community church built in 1907 in Death Valley's most famous ghost "
            "town, which at its peak in 1908 had a population estimated at 10,000 and boasted "
            "electric lights, a stock exchange, and three newspapers. The main gold mine played out "
            "by 1911 and the town was virtually empty by 1920; the church was among the many "
            "buildings that collapsed or were dismantled for salvage. Ruins stand openly on Bureau "
            "of Land Management land alongside the iconic Bottle House."
        ),
        "source": "AURIK",
        "confidence": 0.75,
    },
    {
        "name": "Fairbank Church Ruins, Fairbank, Arizona",
        "type": "abandoned_church",
        "latitude": 31.723,
        "longitude": -110.188,
        "description": (
            "The ruins of a late-19th-century adobe church in the Santa Cruz County railroad ghost "
            "town of Fairbank, which served as a supply hub for Tombstone's silver mines after the "
            "Benson-to-Nogales railroad arrived in the 1880s. After Tombstone's mines flooded and "
            "the railroad rerouted, Fairbank's economic reason for existence disappeared and the "
            "town was slowly abandoned through the 1970s. The church ruins are visible along the San "
            "Pedro Riparian National Conservation Area trail system."
        ),
        "source": "AURIK",
        "confidence": 0.75,
    },
    {
        "name": "San Ignacio Catholic Church, Monticello, New Mexico",
        "type": "abandoned_church",
        "latitude": 33.287,
        "longitude": -107.389,
        "description": (
            "Built in 1869 by the founding Hispanic ranching families of Cañada Alamosa (renamed "
            "Monticello in 1881), this adobe mission church served Sierra County's agricultural "
            "community for over 150 years and holds baptism, marriage, and burial records from 1869 "
            "onward. With fewer than 100 families remaining in the ghost town today versus the 1,000 "
            "who once lived in the canyon, the Catholic Diocese decommissioned the church in 2024 "
            "and gifted it to the Monticello Canyon Association for community use. Structural "
            "deterioration required demolition of the tower in 2025."
        ),
        "source": "AURIK",
        "confidence": 0.75,
    },
    {
        "name": "Santo Niño de Atocha Catholic Church, Cuervo, New Mexico",
        "type": "abandoned_church",
        "latitude": 35.052,
        "longitude": -104.281,
        "description": (
            "Commissioned in 1915 at the height of Cuervo's prosperity as a ranching and railroad "
            "community on old Route 66 in Guadalupe County, this Catholic church served several "
            "hundred residents. As Route 66 was bypassed by Interstate 40 and ranching economics "
            "changed, Cuervo's population collapsed from roughly 500 to under 50; the church became "
            "a near-ghost town relic. The building still stands along the old highway as a landmark "
            "of New Mexico's Route 66 heritage."
        ),
        "source": "AURIK",
        "confidence": 0.75,
    },
    {
        "name": "Santa Rosa de Lima Church Ruins, Abiquiu, New Mexico",
        "type": "abandoned_church",
        "latitude": 36.216,
        "longitude": -106.319,
        "description": (
            "Built around 1744 as the Roman Catholic church of the Spanish colonial plaza settlement "
            "of Santa Rosa de Lima in Rio Arriba County, this adobe structure was part of an early "
            "frontier community established by Hispanic settlers pushing north along the Chama "
            "River. Repeated Ute and Comanche raids forced abandonment of the plaza in 1747, and the "
            "ruins have remained largely intact on Archdiocese of Santa Fe land ever since. Listed "
            "on the National Register of Historic Places, the substantial adobe walls remain a "
            "striking reminder of Spain's northern frontier."
        ),
        "source": "AURIK",
        "confidence": 0.75,
    },
    {
        "name": "Bodie Methodist Church, Bodie, California",
        "type": "abandoned_church",
        "latitude": 38.213,
        "longitude": -119.013,
        "description": (
            "Erected in 1882 to serve a Mono County gold camp that had swelled to perhaps 10,000 "
            "residents during its late-1870s peak, this Methodist church was the center of Bodie's "
            "respectable social life in a town notorious for its lawlessness and saloons. The gold "
            "ran out and Bodie gradually depopulated; the church held its last service in 1932. Now "
            "maintained by California State Parks in a policy of 'arrested decay,' the building "
            "retains original furnishings including its piano."
        ),
        "source": "AURIK",
        "confidence": 0.85,
    },
    {
        "name": "St. Charles Borromeo Catholic Church, Shasta, California",
        "type": "abandoned_church",
        "latitude": 40.602,
        "longitude": -122.493,
        "description": (
            "Built in 1857 to serve the Catholic miners of Shasta, which in the early 1850s was the "
            "largest inland city in California with $100,000 in gold passing through its commercial "
            "district every week. When the California and Oregon Railroad bypassed Shasta in 1872 in "
            "favor of Redding four miles east, the town's commercial district collapsed within "
            "months and the church was abandoned. Brick ruins of St. Charles Borromeo are preserved "
            "within the Shasta State Historic Park managed by California State Parks."
        ),
        "source": "AURIK",
        "confidence": 0.85,
    },
    {
        "name": "Volcano Union Congregational Church, Volcano, California",
        "type": "abandoned_church",
        "latitude": 38.431,
        "longitude": -120.631,
        "description": (
            "Built in 1856 in Amador County's gold rush settlement of Volcano, which claimed "
            "California's first lending library and lending telescope, this Congregational church "
            "served the mining community during its most prosperous decade. As placer gold deposits "
            "exhausted and hydraulic mining declined, Volcano's population shrank from several "
            "thousand to under 100 by the late 19th century, and the church fell out of regular use. "
            "The historic stone building is now preserved in the Volcano ghost town district."
        ),
        "source": "AURIK",
        "confidence": 0.65,
    },
    {
        "name": "Shaniko Community Chapel, Shaniko, Oregon",
        "type": "abandoned_church",
        "latitude": 45.003,
        "longitude": -120.753,
        "description": (
            "A small Protestant frame chapel built around 1901 in what was promoted as the 'Wool "
            "Capital of the World,' when Shaniko in Wasco County shipped more wool than any other "
            "railroad in the Pacific Northwest. After a competing rail line was built in 1911 and "
            "destroyed Shaniko's transport monopoly, the town declined rapidly; a series of fires "
            "accelerated the collapse. The chapel is part of the Shaniko Historic District listed on "
            "the National Register and is occasionally used for special ceremonies."
        ),
        "source": "AURIK",
        "confidence": 0.75,
    },
    {
        "name": "Locust Grove Church, Sherman County, Oregon",
        "type": "abandoned_church",
        "latitude": 45.417,
        "longitude": -120.778,
        "description": (
            "A Protestant community church established around the 1880s to serve the wheat-farming "
            "families of Sherman County's high desert plateau, where homesteaders flocked during the "
            "late-19th-century agricultural expansion along the Columbia River. As farm "
            "consolidation reduced the number of rural families through the mid-20th century, the "
            "congregation dissolved and the community it served became a ghost town. The building is "
            "documented in Oregon historical archives and the Sherman County ghost town records."
        ),
        "source": "AURIK",
        "confidence": 0.65,
    },
    {
        "name": "Elberton United Brethren Church, Elberton, Washington",
        "type": "abandoned_church",
        "latitude": 46.981,
        "longitude": -117.221,
        "description": (
            "Built in 1913 in the ghost town of Elberton, platted in 1886 in Garfield County on a "
            "branch of the Palouse River, this United Brethren in Christ church survived the fires "
            "(1908), floods (1910), railroad pullout (1907), and Great Depression that collectively "
            "emptied the town. By 1966, Elberton was formally disincorporated; the church is now the "
            "last significant standing structure in what was once a community of 500. It draws "
            "photographers and ghost-town explorers and is documented on Atlas Obscura and Spokane "
            "Historical."
        ),
        "source": "AURIK",
        "confidence": 0.85,
    },
    {
        "name": "Sherman Community Church, Sherman, Washington",
        "type": "abandoned_church",
        "latitude": 47.828,
        "longitude": -118.605,
        "description": (
            "A modest Protestant church built in the 1890s in the Lincoln County wheat-farming "
            "hamlet of Sherman, which thrived briefly during the homesteading boom north of Wilbur. "
            "As wheat prices fell and agricultural operations consolidated into larger holdings, the "
            "farming families dispersed and the community shrank to a church, a cemetery, and "
            "scattered foundations. A maintenance group of local descendants gathers annually for a "
            "Memorial Day service, one of the few remaining gatherings at the site."
        ),
        "source": "AURIK",
        "confidence": 0.75,
    },
    {
        "name": "Adams Grove Presbyterian Church, Dallas County, Alabama",
        "type": "abandoned_church",
        "latitude": 32.272,
        "longitude": -87.031,
        "description": (
            "Built in 1853 in the antebellum Greek Revival style near Sardis in Dallas County, this "
            "Presbyterian church features a rare 'distyle-in-antis' portico and four separate "
            "entryways historically used to segregate enslaved people (who entered through side "
            "doors to the balcony) from white congregants. The adjacent cemetery holds burials from "
            "1843 to 1955, and the building was used for its last service in 1974. Listed on the "
            "National Register of Historic Places in 1986, it is one of the least-altered antebellum "
            "rural churches in Alabama."
        ),
        "source": "AURIK",
        "confidence": 0.85,
    },
    {
        "name": "St. Luke's Episcopal Church, Old Cahawba, Alabama",
        "type": "abandoned_church",
        "latitude": 32.319,
        "longitude": -87.105,
        "description": (
            "Designed in 1854 in Carpenter Gothic style by architect Richard Upjohn for Episcopal "
            "worshippers in Alabama's first permanent state capital, this Dallas County church was "
            "dismantled and moved 11 miles to Martin's Station after Cahawba's Civil War decline and "
            "recurring floods. Auburn University's Rural Studio relocated and reassembled it at Old "
            "Cahawba Archaeological Park between 2006–2008 as a preservation project. Listed on the "
            "National Register since 1982, it stands as a central artifact of one of the South's "
            "most evocative ghost towns."
        ),
        "source": "AURIK",
        "confidence": 0.85,
    },
    {
        "name": "Goshen Primitive Baptist Church, Clark County, Kentucky",
        "type": "abandoned_church",
        "latitude": 38.019,
        "longitude": -84.071,
        "description": (
            "Founded in 1797 with 59 charter members at the home of William Payne in Clark County, "
            "this is among the oldest Baptist congregations in Kentucky; the current Greek Revival "
            "brick building dates to around 1850. Primitive Baptists, who reject paid clergy, Sunday "
            "Schools, and musical instruments, saw their rural membership base erode through the "
            "20th century as the surrounding farming community depopulated. Listed on the National "
            "Register of Historic Places in 1979, the congregation now has very limited or no active "
            "membership."
        ),
        "source": "AURIK",
        "confidence": 0.85,
    },
    {
        "name": "Chinn-Scott Chapel, Pointe Coupee Parish, Louisiana",
        "type": "abandoned_church",
        "latitude": 30.78,
        "longitude": -91.658,
        "description": (
            "Founded in 1890 as Chinn Chapel African Methodist Episcopal, with a land deed "
            "formalized in 1903 when the Platt family sold half an acre near Batchelor for $100, "
            "this chapel in Pointe Coupee Parish also briefly served as the first public school for "
            "local Black children during the Jim Crow era. The church was incorporated into the "
            "United Methodist denomination before its congregation was decommissioned in 2015. It "
            "now stands abandoned in the rural bayou landscape as a testament to the African "
            "American religious community of Reconstruction-era Louisiana."
        ),
        "source": "AURIK",
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
                    "source": "AURIK",
                    "confidence": 0.65,
                }
            )
    return results


# ---------------------------------------------------------------------------
# Merge helpers
# ---------------------------------------------------------------------------


def _normalize_name(name: str) -> str:
    """Normalize a location name for fuzzy matching against seed data."""
    import re as _re
    import html as _html
    # Decode HTML entities (e.g. &#8217; → right single quote)
    name = _html.unescape(name)
    # Normalize fancy quotes / apostrophes to plain ASCII
    name = name.replace("\u2018", "'").replace("\u2019", "'").replace("\u201c", '"').replace("\u201d", '"')
    # Strip trailing ", USA" or similar country suffixes
    name = _re.sub(r",?\s+usa\s*$", "", name, flags=_re.IGNORECASE)
    # Remove parenthetical qualifiers used in seed names, e.g. "(Keely)", "(Vernon, CT)"
    name = _re.sub(r"\s*\([^)]*\)", "", name)
    # Normalize "St." / "St " → "st " so abbreviation period doesn't matter
    name = _re.sub(r"\bst\.?(?=\s|\b|,|\.|$)", "st", name, flags=_re.IGNORECASE)
    return _re.sub(r"\s+", " ", name).strip().lower()


def _build_seed_lookup() -> Dict[str, Dict[str, Any]]:
    """Return a dict mapping normalized seed names to their full seed records."""
    return {_normalize_name(entry["name"]): entry for entry in SEED_CHURCHES}


def _merge_scraped_with_seed(
    scraped: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Enrich scraped entries with seed data coordinates and descriptions.

    Strategy:
    1. For each scraped entry, attempt a name-normalised lookup in SEED_CHURCHES.
    2. If found, replace the scraped record with the full seed record (which has
       web-researched coordinates and a proper historical description).
    3. Any seed entries *not* represented in the scraped list are appended so
       the output always includes the full supplemental dataset.
    4. Any scraped entries with no seed match are kept as-is (null coords).
    """
    seed_lookup = _build_seed_lookup()
    output: List[Dict[str, Any]] = []
    matched_seed_keys: set = set()

    for scraped_entry in scraped:
        key = _normalize_name(scraped_entry["name"])
        if key in seed_lookup:
            output.append(seed_lookup[key])
            matched_seed_keys.add(key)
        else:
            # New entry not yet in seed — include with whatever data we have
            output.append(scraped_entry)

    # Append supplemental seed entries not matched above
    for entry in SEED_CHURCHES:
        if _normalize_name(entry["name"]) not in matched_seed_keys:
            output.append(entry)

    return output


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
        description="Fetch or generate an abandoned churches dataset for Aurik."
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
        scraped = scrape_obsidian_urbex()
        if scraped:
            # Enrich scraped entries with web-researched coordinates from seed,
            # and append the full supplemental dataset.
            churches = _merge_scraped_with_seed(scraped)
            method_used = "obsidian_urbex_scrape+seed_enriched"

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
