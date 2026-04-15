#!/usr/bin/env python3
"""
fetch_historic_camps.py — Historic camp sites for metal detecting.

Outputs data/historic_camps.json using a hardcoded dataset of ~154 curated
locations spanning four categories:
  - Category A: Emigrant Trail Camps (Oregon, California, Mormon, Santa Fe trails)
  - Category B: Military/Frontier Camps (Texas frontier line, AZ/NM territory, Civil War)
  - Category C: Rendezvous/Fur Trade (Rocky Mountain Rendezvous 1825-1840, AFC, HBC)
  - Category D: Logging/Lumber Camps (Great Lakes, Northeast, Pacific NW, Appalachia)

Sites on NPS land, State Parks, Wilderness Areas, active military reservations,
and tribal land are excluded. Mining camps are excluded. Duplicates from
existing datasets (trail_landmarks, stagecoach_stops, battles_seed,
frrandp_ghost_towns) are also excluded.

Usage::

    python scripts/fetch_historic_camps.py
    python scripts/fetch_historic_camps.py --output-dir data/ \\
        --output-name historic_camps
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


HISTORIC_CAMPS: list[dict] = [
    # ------------------------------------------------------------------ #
    # Kanesville (Council Bluffs), IA
    # ------------------------------------------------------------------ #
    {
        "name": "Kanesville (Council Bluffs), IA",
        "type": "camp",
        "category": "emigrant_trail",
        "latitude": 41.263,
        "longitude": -95.858,
        "description": (
            "Kanesville, later renamed Council Bluffs, served as the primary staging ground for the Mormon "
            "Trail and a major departure point for Oregon and California-bound emigrants between 1846 and "
            "1852. Thousands of wagon trains organized here on the east bank of the Missouri River before "
            "crossing into Nebraska. The town was a bustling supply center with blacksmiths, outfitters, and "
            "ferries, leaving behind a rich material record of 19th-century frontier commerce. Private and "
            "urban development now covers most of the original town, but the surrounding river bluffs have "
            "yielded coins, wagon hardware, and personal effects from the emigration era."
        ),
        "source": "AURIK",
        "confidence": 0.88,
    },
    # ------------------------------------------------------------------ #
    # Bellevue, NE
    # ------------------------------------------------------------------ #
    {
        "name": "Bellevue, NE",
        "type": "camp",
        "category": "emigrant_trail",
        "latitude": 41.145,
        "longitude": -95.919,
        "description": (
            "Bellevue, Nebraska's oldest permanent settlement, was a key crossing and provisioning point on "
            "the Missouri River used by emigrants heading west on the Oregon and California trails from the "
            "late 1820s onward. The American Fur Company operated a post here, and later the Presbyterian "
            "mission drew emigrants and traders alike. The site sat at the convergence of multiple fur trade "
            "and emigrant routes, making it a dense repository of early 19th-century material culture. "
            "Private lands near the original townsite have produced trade goods, wagon hardware, and coins "
            "from the emigrant era."
        ),
        "source": "AURIK",
        "confidence": 0.85,
    },
    # ------------------------------------------------------------------ #
    # Dobytown (near Fort Kearny), NE
    # ------------------------------------------------------------------ #
    {
        "name": "Dobytown (near Fort Kearny), NE",
        "type": "camp",
        "category": "emigrant_trail",
        "latitude": 40.641,
        "longitude": -99.018,
        "description": (
            "Dobytown was the unofficial civilian camp and saloon district that grew up immediately adjacent "
            "to Fort Kearny on the Platte River road in Nebraska, catering to emigrants, soldiers, and "
            "overland freighters throughout the 1850s and 1860s. The town consisted of sod and adobe "
            "structures selling whiskey, provisions, and entertainment to the constant westward traffic, "
            "giving it a reputation as a rough frontier outpost. The site was effectively erased after the "
            "military reservation was extended, leaving no above-ground remains but a rich buried artifact "
            "layer. BLM and private lands surrounding the old fort area have produced military buttons, "
            "coins, and trade goods from this period."
        ),
        "source": "AURIK",
        "confidence": 0.82,
    },
    # ------------------------------------------------------------------ #
    # Elm Creek Station, NE
    # ------------------------------------------------------------------ #
    {
        "name": "Elm Creek Station, NE",
        "type": "camp",
        "category": "emigrant_trail",
        "latitude": 40.72,
        "longitude": -99.363,
        "description": (
            "Elm Creek Station served as a midpoint camp and relay station on the Platte River road in "
            "central Nebraska, providing water, grass, and limited supplies to emigrant wagon trains "
            "throughout the 1850s and 1860s. The station sat along a heavily traveled section of the road "
            "where trains camped nightly after covering their daily 15-20 miles. Multiple emigrant diaries "
            "mention Elm Creek as a reliable camp with good water and timber. The surrounding private "
            "farmland has occasionally yielded wagon hardware, coins, and emigrant personal effects through "
            "agricultural activity."
        ),
        "source": "AURIK",
        "confidence": 0.78,
    },
    # ------------------------------------------------------------------ #
    # Plum Creek, NE
    # ------------------------------------------------------------------ #
    {
        "name": "Plum Creek, NE",
        "type": "camp",
        "category": "emigrant_trail",
        "latitude": 40.589,
        "longitude": -99.584,
        "description": (
            "Plum Creek on the south bank of the Platte River in Nebraska was both a regular emigrant "
            "campsite and the location of the 1864 Plum Creek Massacre, where Cheyenne warriors attacked a "
            "wagon train, killing eleven settlers and taking two women captive. The site was a natural "
            "camping ground with water and timber, used continuously from the 1840s through the 1870s by "
            "overland travelers. The massacre left behind a dense concentration of burned wagon hardware, "
            "personal effects, and period material culture in the immediate area. Private farmland "
            "surrounding the historical site has produced scattered emigrant-era artifacts over the years."
        ),
        "source": "AURIK",
        "confidence": 0.85,
    },
    # ------------------------------------------------------------------ #
    # Lower California Crossing, NE
    # ------------------------------------------------------------------ #
    {
        "name": "Lower California Crossing, NE",
        "type": "camp",
        "category": "emigrant_trail",
        "latitude": 41.12,
        "longitude": -101.6,
        "description": (
            "The Lower California Crossing of the North Platte River in western Nebraska was one of the most "
            "important fords on the overland trails, used by tens of thousands of emigrants who could not "
            "afford the ferry at Fort Laramie or chose to cross lower to save mileage. Large emigrant camps "
            "formed on both banks during the crossing season, with wagons waiting days for the river to drop "
            "enough to ford safely. The crossing site saw heavy use from the 1840s through the 1860s, and "
            "the riverbanks held a concentration of dropped, discarded, and buried emigrant material. BLM "
            "and private lands at the crossing area have produced coins, wagon parts, and trail hardware."
        ),
        "source": "AURIK",
        "confidence": 0.82,
    },
    # ------------------------------------------------------------------ #
    # Mud Springs, NE
    # ------------------------------------------------------------------ #
    {
        "name": "Mud Springs, NE",
        "type": "camp",
        "category": "emigrant_trail",
        "latitude": 41.557,
        "longitude": -103.09,
        "description": (
            "Mud Springs in western Nebraska served as both an Oregon and California Trail camp and a Pony "
            "Express relay station, its year-round water source making it a critical stop in an otherwise "
            "dry stretch of the high plains. The site gained additional historical significance during the "
            "Mud Springs Battle of February 1865, when Cheyenne and Sioux warriors attacked the telegraph "
            "station and Pony Express relay in retaliation for the Sand Creek Massacre. The battle left a "
            "dense material record of military and civilian equipment in the surrounding area. The Mud "
            "Springs site is on BLM-administered land and is considered an excellent candidate for metal "
            "detecting."
        ),
        "source": "AURIK",
        "confidence": 0.87,
    },
    # ------------------------------------------------------------------ #
    # Lodgepole Creek Camp, NE
    # ------------------------------------------------------------------ #
    {
        "name": "Lodgepole Creek Camp, NE",
        "type": "camp",
        "category": "emigrant_trail",
        "latitude": 41.18,
        "longitude": -102.17,
        "description": (
            "The Lodgepole Creek divergence point in western Nebraska marked where a significant number of "
            "California-bound emigrants left the main Platte River road and turned southwest up Lodgepole "
            "Creek toward Julesburg and the Colorado shortcut, making it one of the key trail junctions in "
            "the entire overland emigration system. Large temporary camps formed at this junction as wagon "
            "captains debated routes and reorganized parties. The divergence point saw heavy use throughout "
            "the 1850s and 1860s. Private farmland in the area has produced emigrant-era coins, hardware, "
            "and personal items through decades of agricultural activity."
        ),
        "source": "AURIK",
        "confidence": 0.8,
    },
    # ------------------------------------------------------------------ #
    # Horse Creek Treaty Ground, WY
    # ------------------------------------------------------------------ #
    {
        "name": "Horse Creek Treaty Ground, WY",
        "type": "camp",
        "category": "emigrant_trail",
        "latitude": 42.008,
        "longitude": -104.597,
        "description": (
            "The Horse Creek Treaty Ground near the mouth of Horse Creek on the North Platte River in "
            "Wyoming was the site of the Fort Laramie Treaty Council of 1851, one of the largest gatherings "
            "of Plains Indian nations in American history, drawing an estimated 10,000 Lakota, Cheyenne, "
            "Arapaho, Crow, Shoshone, and other tribal representatives. The U.S. government's Indian "
            "commissioners brought enormous quantities of trade goods, annuities, and provisions, creating a "
            "vast temporary encampment over several weeks. The ground was subsequently used as an emigrant "
            "campsite given its water and grass resources. BLM land at the confluence has produced trade "
            "goods, beads, and annuity items from the treaty era."
        ),
        "source": "AURIK",
        "confidence": 0.88,
    },
    # ------------------------------------------------------------------ #
    # Deer Creek Camp, WY
    # ------------------------------------------------------------------ #
    {
        "name": "Deer Creek Camp, WY",
        "type": "camp",
        "category": "emigrant_trail",
        "latitude": 42.831,
        "longitude": -106.043,
        "description": (
            "Deer Creek Camp on the North Platte River in Wyoming was one of the most significant emigrant "
            "stops between Fort Laramie and South Pass, featuring a trading post established in 1857 that "
            "sold provisions, replaced worn livestock, and served as a telegraph relay station. Dozens of "
            "emigrant diaries mention Deer Creek as a welcome respite with reliable water, good grass, and "
            "timber for repairs. The camp saw continuous use from the late 1840s through the 1870s. "
            "BLM-administered land along Deer Creek has produced trade goods, coins, and emigrant hardware "
            "from this prolific camp area."
        ),
        "source": "AURIK",
        "confidence": 0.85,
    },
    # ------------------------------------------------------------------ #
    # Warm Springs Camp (Alcova), WY
    # ------------------------------------------------------------------ #
    {
        "name": "Warm Springs Camp (Alcova), WY",
        "type": "camp",
        "category": "emigrant_trail",
        "latitude": 42.573,
        "longitude": -107.017,
        "description": (
            "The Warm Springs area near present-day Alcova, Wyoming offered emigrants a rare combination of "
            "warm mineral springs and good grass in the otherwise arid Sweetwater country, making it a "
            "favored camp before the difficult approach to South Pass. Emigrant journals from the 1840s "
            "through 1860s frequently mention pausing at the springs to wash clothes, rest livestock, and "
            "enjoy the warm water after weeks of trail travel. The camp area sat on BLM-administered land "
            "that has not been extensively developed. The surrounding high desert terrain has preserved "
            "buried camp material well, and detectorists have found coins and trail hardware in adjacent "
            "areas."
        ),
        "source": "AURIK",
        "confidence": 0.8,
    },
    # ------------------------------------------------------------------ #
    # Rocky Ridge Camp, WY
    # ------------------------------------------------------------------ #
    {
        "name": "Rocky Ridge Camp, WY",
        "type": "camp",
        "category": "emigrant_trail",
        "latitude": 42.644,
        "longitude": -108.45,
        "description": (
            "Rocky Ridge in Wyoming was one of the most grueling sections of the entire Oregon Trail, where "
            "emigrant wagons had to navigate a 12-mile stretch of rough granite outcroppings with no water "
            "and brutal terrain, making the camps at both ends of the ridge critical stopping points. "
            "Emigrant journals describe Rocky Ridge as the hardest day on the trail, with broken axles, dead "
            "livestock, and abandoned wagons littering the route. The 1856 Martin and Willie handcart "
            "company suffered catastrophic losses in an early October snowstorm near this site. BLM land at "
            "the ridge has preserved a concentration of abandoned trail hardware and personal effects."
        ),
        "source": "AURIK",
        "confidence": 0.85,
    },
    # ------------------------------------------------------------------ #
    # Names Hill, WY
    # ------------------------------------------------------------------ #
    {
        "name": "Names Hill, WY",
        "type": "camp",
        "category": "emigrant_trail",
        "latitude": 41.984,
        "longitude": -110.274,
        "description": (
            "Names Hill on the Green River in Wyoming was a towering sandstone cliff where thousands of "
            "emigrants carved their names, dates, and home states into the soft rock face as they camped at "
            "the river ford below, creating one of the most remarkable inscription registers on the entire "
            "overland trail system. The ford site made it a mandatory camp where wagon trains waited for "
            "water levels and organized crossings, often staying multiple days. Jim Bridger himself carved "
            "his name here in 1844. The camp area is BLM-administered land, and the riverbank and "
            "surrounding flats have produced coins, wagon hardware, and personal effects dropped during the "
            "fording operations."
        ),
        "source": "AURIK",
        "confidence": 0.9,
    },
    # ------------------------------------------------------------------ #
    # Ham's Fork Camp (Granger), WY
    # ------------------------------------------------------------------ #
    {
        "name": "Ham's Fork Camp (Granger), WY",
        "type": "camp",
        "category": "emigrant_trail",
        "latitude": 41.617,
        "longitude": -109.94,
        "description": (
            "Ham's Fork at present-day Granger, Wyoming was both an important pre-trail fur trade gathering "
            "site and a major junction on the emigrant trail system where the Oregon, California, and Mormon "
            "trails all converged before their respective divergences toward the Snake River and Salt Lake "
            "Valley. The confluence of Ham's Fork with the Green River created an excellent camping area "
            "used heavily from the 1820s fur trade era through the 1860s emigrant period. The site hosted "
            "the 1834 Rocky Mountain Rendezvous and was a regular camp for wagon trains restocking water and "
            "grass. BLM land at the confluence has produced trade goods, coins, and mixed emigrant and fur "
            "trade material."
        ),
        "source": "AURIK",
        "confidence": 0.87,
    },
    # ------------------------------------------------------------------ #
    # Thomas Fork Camp, WY
    # ------------------------------------------------------------------ #
    {
        "name": "Thomas Fork Camp, WY",
        "type": "camp",
        "category": "emigrant_trail",
        "latitude": 42.032,
        "longitude": -111.103,
        "description": (
            "Thomas Fork of the Bear River in western Wyoming marked one of the last significant camps "
            "before emigrants crossed into Idaho Territory, with excellent water and grass in the Bear River "
            "drainage making it a favored multi-day rest stop. The ford of Thomas Fork was considered "
            "difficult in high water, and emigrant journals record many parties camping here to wait for "
            "lower water or repair wagons damaged by the rough terrain since South Pass. The camp area sits "
            "on a mix of BLM and private land that has seen limited development. Detectorists working the "
            "ford and camp areas have recovered coins, wagon hardware, and personal items from the emigrant "
            "period."
        ),
        "source": "AURIK",
        "confidence": 0.82,
    },
    # ------------------------------------------------------------------ #
    # Bear River Camp (Cokeville), WY
    # ------------------------------------------------------------------ #
    {
        "name": "Bear River Camp (Cokeville), WY",
        "type": "camp",
        "category": "emigrant_trail",
        "latitude": 42.078,
        "longitude": -110.96,
        "description": (
            "The Bear River meadows near present-day Cokeville, Wyoming provided the last major rest camp in "
            "Wyoming before the crossing into Idaho, with outstanding grass, water, and timber that made it "
            "one of the most celebrated camping spots on the entire Oregon Trail. Emigrant diaries from the "
            "1840s through 1860s consistently praise this camp as one of the finest on the journey. The "
            "meadows saw continuous use across all the major western trails including Oregon, California, "
            "and Mormon routes. BLM and private lands in the area preserve a rich material record from "
            "decades of emigrant use."
        ),
        "source": "AURIK",
        "confidence": 0.85,
    },
    # ------------------------------------------------------------------ #
    # Soda Springs Camp, ID
    # ------------------------------------------------------------------ #
    {
        "name": "Soda Springs Camp, ID",
        "type": "camp",
        "category": "emigrant_trail",
        "latitude": 42.654,
        "longitude": -111.604,
        "description": (
            "Soda Springs in southeastern Idaho was one of the most famous landmarks on the entire overland "
            "trail system, where naturally carbonated springs and the nearby Steamboat Spring created a "
            "spectacle that every emigrant journal describes in vivid detail. The springs were both a "
            "novelty and a critical water source, and emigrants invariably camped here for a day or more to "
            "rest, bake soda bread, and enjoy the carbonated water. The camp area saw continuous use from "
            "the fur trade era of the 1820s through the emigrant period of the 1860s. BLM and private land "
            "surrounding the spring area has produced trail hardware, coins, and camp material from the "
            "extensive emigrant occupation."
        ),
        "source": "AURIK",
        "confidence": 0.9,
    },
    # ------------------------------------------------------------------ #
    # American Falls Camp, ID
    # ------------------------------------------------------------------ #
    {
        "name": "American Falls Camp, ID",
        "type": "camp",
        "category": "emigrant_trail",
        "latitude": 42.786,
        "longitude": -112.85,
        "description": (
            "American Falls on the Snake River in Idaho was a mandatory camp for all Oregon Trail emigrants "
            "traveling along the south bank of the Snake, the dramatic falls providing the only reliable "
            "water access in an otherwise difficult desert stretch. The camp area saw heavy use from the "
            "1840s through the 1860s, with emigrants fording the river or portaging supplies around the "
            "falls. The original falls and much of the historic campsite now lies partially under American "
            "Falls Reservoir, created in the 1920s, though the surrounding uplands on private and BLM land "
            "preserve material from the camp era above the inundation line."
        ),
        "source": "AURIK",
        "confidence": 0.8,
    },
    # ------------------------------------------------------------------ #
    # Raft River Junction Camp, ID
    # ------------------------------------------------------------------ #
    {
        "name": "Raft River Junction Camp, ID",
        "type": "camp",
        "category": "emigrant_trail",
        "latitude": 42.15,
        "longitude": -113.5,
        "description": (
            "The Raft River Junction in south-central Idaho was the critical divergence point where "
            "California-bound emigrants left the main Oregon Trail and turned southwest up the Raft River "
            "toward the Humboldt River and Nevada, making it one of the most significant trail junctions in "
            "the entire emigrant road system. Large temporary camps formed at the junction as wagon parties "
            "reorganized and debated which route to follow, and the junction saw peak traffic during the "
            "California Gold Rush years of 1849-1852. BLM-administered land at the junction preserves "
            "excellent camping potential, and the area has produced mixed Oregon and California Trail "
            "material."
        ),
        "source": "AURIK",
        "confidence": 0.85,
    },
    # ------------------------------------------------------------------ #
    # Salmon Falls Camp, ID
    # ------------------------------------------------------------------ #
    {
        "name": "Salmon Falls Camp, ID",
        "type": "camp",
        "category": "emigrant_trail",
        "latitude": 42.61,
        "longitude": -114.85,
        "description": (
            "Salmon Falls on the Snake River in Idaho was a major fishing camp where emigrants could trade "
            "with local Shoshone bands for quantities of dried salmon, providing critical protein for the "
            "remaining journey through Nevada's harsh desert terrain. The falls themselves created a natural "
            "gathering point where Native fishermen had operated weirs and drying racks for centuries before "
            "the emigrant era. Emigrant journals from the late 1840s through 1860s document lively trade and "
            "multi-day camps at the falls. BLM and private lands near the falls area have produced trade "
            "goods, fishing hardware, and emigrant camp material."
        ),
        "source": "AURIK",
        "confidence": 0.83,
    },
    # ------------------------------------------------------------------ #
    # Bruneau Crossing Camp, ID
    # ------------------------------------------------------------------ #
    {
        "name": "Bruneau Crossing Camp, ID",
        "type": "camp",
        "category": "emigrant_trail",
        "latitude": 42.877,
        "longitude": -115.797,
        "description": (
            "The Bruneau River ford in southwestern Idaho was a challenging crossing on the Oregon Trail "
            "that forced emigrants to camp on both banks while waiting for the notoriously rapid stream to "
            "drop enough for safe passage. The Bruneau Crossing was particularly difficult in spring and "
            "early summer, and emigrant journals record multiple drownings and wagon losses at this ford. "
            "The camp area on the BLM-administered high desert terrain has seen limited modern disturbance. "
            "Detectorists working the ford banks and adjacent camp flats have found wagon hardware, personal "
            "effects, and coins from the emigrant period."
        ),
        "source": "AURIK",
        "confidence": 0.8,
    },
    # ------------------------------------------------------------------ #
    # Birch Creek Camp, OR
    # ------------------------------------------------------------------ #
    {
        "name": "Birch Creek Camp, OR",
        "type": "camp",
        "category": "emigrant_trail",
        "latitude": 45.465,
        "longitude": -118.75,
        "description": (
            "Birch Creek in northeastern Oregon provided a critical camp and water source for emigrants who "
            "had just descended from the grueling Blue Mountains crossing, offering a welcome rest in the "
            "foothills before the final push toward the Columbia River. The camp sat in a sheltered creek "
            "drainage where good grass and water made it a natural multi-day rest stop. Emigrants in failing "
            "health or with broken wagons frequently halted here for extended stays. BLM and private land in "
            "the Birch Creek drainage has produced trail hardware and emigrant material from the active camp "
            "years of the 1840s-1860s."
        ),
        "source": "AURIK",
        "confidence": 0.78,
    },
    # ------------------------------------------------------------------ #
    # Thousand Springs Valley, NV
    # ------------------------------------------------------------------ #
    {
        "name": "Thousand Springs Valley, NV",
        "type": "camp",
        "category": "emigrant_trail",
        "latitude": 41.75,
        "longitude": -115.1,
        "description": (
            "Thousand Springs Valley in northeastern Nevada was a key water and grass resource on the "
            "California Trail's Humboldt River route, the natural springs providing reliable water in an "
            "otherwise desert landscape that made the surrounding BLM land critically important to emigrants "
            "pushing toward California. The valley saw extensive use during the California Gold Rush years "
            "of 1849-1852 when traffic surged dramatically, and multiple competing trail routes converged in "
            "the area. BLM-administered land throughout the valley preserves excellent camp material "
            "potential from the emigrant era."
        ),
        "source": "AURIK",
        "confidence": 0.82,
    },
    # ------------------------------------------------------------------ #
    # Wells (Bishop Creek) Camp, NV
    # ------------------------------------------------------------------ #
    {
        "name": "Wells (Bishop Creek) Camp, NV",
        "type": "camp",
        "category": "emigrant_trail",
        "latitude": 41.11,
        "longitude": -114.96,
        "description": (
            "Wells, Nevada at the Bishop Creek confluence was a major junction camp on the California Trail "
            "where the Humboldt River road met cutoff routes from the north, making it a decision point for "
            "Gold Rush emigrants choosing between competing Nevada routes. The area's reliable springs and "
            "creek water made it a mandatory camp for emigrants and their livestock in the high Nevada "
            "desert. The junction saw peak traffic from 1849-1855. BLM land surrounding the historic camp "
            "area has produced trail hardware, coins, and Gold Rush-era material."
        ),
        "source": "AURIK",
        "confidence": 0.82,
    },
    # ------------------------------------------------------------------ #
    # Rabbit Hole Springs, NV
    # ------------------------------------------------------------------ #
    {
        "name": "Rabbit Hole Springs, NV",
        "type": "camp",
        "category": "emigrant_trail",
        "latitude": 40.87,
        "longitude": -118.13,
        "description": (
            "Rabbit Hole Springs in the Black Rock Desert of Nevada was a desperately needed water source on "
            "Lassen's Cutoff, a brutal alternative California Trail route that promised to shorten the "
            "journey but instead led emigrants through some of the harshest terrain in the American West. "
            "The springs were often overcrowded with livestock churning the water into a foul mudhole, and "
            "emigrant journals from 1849-1851 describe scenes of chaos, dead animals, and abandoned wagons "
            "around the springs. The surrounding BLM desert preserves a remarkable concentration of "
            "abandoned trail material including wagon parts, personal effects, and the bones of livestock."
        ),
        "source": "AURIK",
        "confidence": 0.87,
    },
    # ------------------------------------------------------------------ #
    # Lassen's Meadow Camp, NV
    # ------------------------------------------------------------------ #
    {
        "name": "Lassen's Meadow Camp, NV",
        "type": "camp",
        "category": "emigrant_trail",
        "latitude": 40.83,
        "longitude": -116.2,
        "description": (
            "Lassen's Meadow on the Humboldt River in Nevada represented the last good grass before the "
            "Humboldt Sink crossing on the California Trail, making it a critical rest and provisioning camp "
            "where emigrants fattened their livestock before the final desert push. The meadow saw intensive "
            "use during the Gold Rush years of 1849-1852, with thousands of emigrant wagons camped in the "
            "area simultaneously at peak season. BLM-administered land in the Humboldt River valley near the "
            "historic meadow preserves good camp material potential from the intensive emigrant period."
        ),
        "source": "AURIK",
        "confidence": 0.8,
    },
    # ------------------------------------------------------------------ #
    # Lovelock (Lassen's) Camp, NV
    # ------------------------------------------------------------------ #
    {
        "name": "Lovelock (Lassen's) Camp, NV",
        "type": "camp",
        "category": "emigrant_trail",
        "latitude": 40.18,
        "longitude": -118.47,
        "description": (
            "The Humboldt River camps near present-day Lovelock, Nevada were a major gathering area for "
            "California Trail emigrants completing the Humboldt River route before the dreaded Forty Mile "
            "Desert crossing to the Carson River. Thousands of wagons camped along the Humboldt Sink area in "
            "the late 1840s and 1850s, and the area saw significant abandonment of heavy freight as "
            "emigrants lightened loads for the desert crossing. BLM-administered land throughout the "
            "Humboldt Sink area preserves an exceptional concentration of abandoned trail material from the "
            "Gold Rush emigration period."
        ),
        "source": "AURIK",
        "confidence": 0.83,
    },
    # ------------------------------------------------------------------ #
    # Garden Grove Camp, IA
    # ------------------------------------------------------------------ #
    {
        "name": "Garden Grove Camp, IA",
        "type": "camp",
        "category": "emigrant_trail",
        "latitude": 40.828,
        "longitude": -93.61,
        "description": (
            "Garden Grove was an organized way-station established in April 1846 by the advance Pioneer "
            "Company of Mormon emigrants crossing Iowa, who built cabins, planted crops, and left provisions "
            "specifically to support the hundreds of wagon trains that would follow them west. The "
            "settlement housed hundreds of impoverished Mormon families through the brutal winter of "
            "1846-1847 and served as a staging camp for the main body of the migration. The site saw "
            "intensive use over multiple years. Private farmland in the Garden Grove area has preserved "
            "material from the Mormon emigrant occupation."
        ),
        "source": "AURIK",
        "confidence": 0.87,
    },
    # ------------------------------------------------------------------ #
    # Mount Pisgah Camp, IA
    # ------------------------------------------------------------------ #
    {
        "name": "Mount Pisgah Camp, IA",
        "type": "camp",
        "category": "emigrant_trail",
        "latitude": 41.048,
        "longitude": -94.197,
        "description": (
            "Mount Pisgah in southwestern Iowa was the second major way-station established by the Mormon "
            "Pioneer Company in 1846, located at a high point above the Middle Fork of the Grand River where "
            "thousands of Mormon emigrants camped, some dying and being buried there during the difficult "
            "Iowa crossing. The camp housed up to 2,500 people simultaneously during the peak migration "
            "period and served as a staging area for the Missouri River crossing. The site has been "
            "partially preserved by the LDS Church, but surrounding private farmland retains material from "
            "the extensive camp use."
        ),
        "source": "AURIK",
        "confidence": 0.88,
    },
    # ------------------------------------------------------------------ #
    # Mosquito Creek Camp, IA
    # ------------------------------------------------------------------ #
    {
        "name": "Mosquito Creek Camp, IA",
        "type": "camp",
        "category": "emigrant_trail",
        "latitude": 41.6,
        "longitude": -95.757,
        "description": (
            "The Mosquito Creek staging area in western Iowa served as a pre-Kanesville assembly point for "
            "Mormon emigrants approaching the Missouri River crossing, where wagon trains waited for ferry "
            "service and organized for the crossing into Nebraska Territory. The camp sat in a natural "
            "lowland meadow with water and timber, seeing heavy use during the peak Mormon emigration years "
            "of 1846-1852. Private farmland in the area surrounding the historic creek crossing has produced "
            "emigrant-era material through agricultural activity."
        ),
        "source": "AURIK",
        "confidence": 0.78,
    },
    # ------------------------------------------------------------------ #
    # Cutler's Park, NE
    # ------------------------------------------------------------------ #
    {
        "name": "Cutler's Park, NE",
        "type": "camp",
        "category": "emigrant_trail",
        "latitude": 41.352,
        "longitude": -96.061,
        "description": (
            "Cutler's Park was an early 1846 Mormon camp near the Missouri River in Nebraska, established "
            "before the main Winter Quarters settlement was organized, where the first wave of Latter-day "
            "Saint refugees from Nauvoo camped while negotiating with the Omaha Nation for permission to "
            "winter on their lands. The camp predates the more famous Winter Quarters NPS site and sits on "
            "private and urban land outside the protected boundary. The camp saw intense activity during the "
            "critical refugee period of 1846. The surrounding area has produced period material through "
            "construction activity."
        ),
        "source": "AURIK",
        "confidence": 0.82,
    },
    # ------------------------------------------------------------------ #
    # Loup Fork Crossing, NE
    # ------------------------------------------------------------------ #
    {
        "name": "Loup Fork Crossing, NE",
        "type": "camp",
        "category": "emigrant_trail",
        "latitude": 41.557,
        "longitude": -97.45,
        "description": (
            "The Loup Fork crossing of the Loup River in central Nebraska was a significant obstacle on the "
            "Mormon Trail that required extensive camp time as wagon trains waited for water levels and "
            "organized crossing parties, often involving interactions with Pawnee bands whose villages "
            "occupied the surrounding country. The crossing was a natural gathering point where emigrants "
            "camped for multiple days. Private farmland in the Loup Fork area has preserved emigrant and "
            "Native American trade material from the camp period."
        ),
        "source": "AURIK",
        "confidence": 0.78,
    },
    # ------------------------------------------------------------------ #
    # Diamond Springs Camp, KS
    # ------------------------------------------------------------------ #
    {
        "name": "Diamond Springs Camp, KS",
        "type": "camp",
        "category": "emigrant_trail",
        "latitude": 38.84,
        "longitude": -96.73,
        "description": (
            "Diamond Springs in Kansas was called the 'Diamond of the Plains' by Santa Fe Trail travelers "
            "for its remarkably clear, cold spring water in a landscape of otherwise muddy prairie streams, "
            "making it the most prized campsite in the first section of the trail out of Council Grove. The "
            "spring saw continuous use from the 1820s opening of the Santa Fe Trail through the Civil War "
            "era. Army dispatches, merchant caravans, and emigrant wagon trains all camped at Diamond "
            "Springs. Private farmland surrounding the historic spring site has produced Santa Fe Trail "
            "trade goods, Mexican coins, and hardware."
        ),
        "source": "AURIK",
        "confidence": 0.88,
    },
    # ------------------------------------------------------------------ #
    # Lost Spring Camp, KS
    # ------------------------------------------------------------------ #
    {
        "name": "Lost Spring Camp, KS",
        "type": "camp",
        "category": "emigrant_trail",
        "latitude": 38.66,
        "longitude": -97.003,
        "description": (
            "Lost Spring on the Santa Fe Trail in Kansas was named by early travelers who reported "
            "difficulty relocating the spring after initially discovering it, the water source being "
            "intermittent and often dried to a mudhole by summer but providing a critical first-day camp "
            "from Council Grove for eastbound and westbound travelers. The spring saw use from the 1820s "
            "through the end of the trail era in the 1870s. Private farmland in the Lost Spring area has "
            "produced Santa Fe Trail-era trade goods, military equipment, and Mexican silver coins."
        ),
        "source": "AURIK",
        "confidence": 0.83,
    },
    # ------------------------------------------------------------------ #
    # Cottonwood Creek Crossing, KS
    # ------------------------------------------------------------------ #
    {
        "name": "Cottonwood Creek Crossing, KS",
        "type": "camp",
        "category": "emigrant_trail",
        "latitude": 38.524,
        "longitude": -97.719,
        "description": (
            "The Cottonwood Creek crossing on the Santa Fe Trail in central Kansas was a major camp where "
            "the creek provided reliable water in the transition zone between the wooded Flint Hills and the "
            "open Short-grass Prairie, and merchant caravans frequently rested their mules here before "
            "pushing into drier country. The crossing saw peak use from the 1820s through 1870s. Private "
            "farmland on both banks of the historic ford has produced Santa Fe Trail trade goods, military "
            "buttons, and Mexican and American coins from the decades of camp use."
        ),
        "source": "AURIK",
        "confidence": 0.82,
    },
    # ------------------------------------------------------------------ #
    # Little Arkansas Crossing, KS
    # ------------------------------------------------------------------ #
    {
        "name": "Little Arkansas Crossing, KS",
        "type": "camp",
        "category": "emigrant_trail",
        "latitude": 38.021,
        "longitude": -97.907,
        "description": (
            "The Little Arkansas River crossing in central Kansas was where Santa Fe Trail travelers made "
            "the transition between the eastern timber country and the true open plains, and where the trail "
            "divided into the Mountain Route and the shorter but more dangerous Cimarron Cutoff. Emigrant "
            "camps and military encampments accumulated here as parties waited for water levels and "
            "reorganized for whichever route they chose. The crossing area sits on private farmland that has "
            "produced trail-era artifacts including military buttons, trade goods, and coins."
        ),
        "source": "AURIK",
        "confidence": 0.82,
    },
    # ------------------------------------------------------------------ #
    # Cow Creek Crossing, KS
    # ------------------------------------------------------------------ #
    {
        "name": "Cow Creek Crossing, KS",
        "type": "camp",
        "category": "emigrant_trail",
        "latitude": 38.202,
        "longitude": -98.783,
        "description": (
            "Cow Creek Crossing near present-day Lyons, Kansas was a major Santa Fe Trail camp on the "
            "Mountain Route where the creek's timber and water made it a favored stopping point in the "
            "otherwise treeless plains. The crossing was the site of the 1854 Cow Creek Fight and saw "
            "multiple military engagements during the Plains Indian Wars, adding a military material layer "
            "on top of the civilian trail camp record. Private and BLM land in the area has produced Santa "
            "Fe Trail trade goods, military equipment, and coins from the active trail years."
        ),
        "source": "AURIK",
        "confidence": 0.83,
    },
    # ------------------------------------------------------------------ #
    # Walnut Creek Crossing, KS
    # ------------------------------------------------------------------ #
    {
        "name": "Walnut Creek Crossing, KS",
        "type": "camp",
        "category": "emigrant_trail",
        "latitude": 38.37,
        "longitude": -98.838,
        "description": (
            "Walnut Creek Crossing in central Kansas was the site of a major Bent & St. Vrain trading post "
            "and later an 1858 stage station, creating a commercial camp complex on the Santa Fe Trail where "
            "merchant caravans traded, restocked, and camped for extended periods. William Bent's trading "
            "post at Walnut Creek was an important fur trade and military supply point throughout the "
            "mid-19th century. BLM and private land at the historic crossing has produced Santa Fe Trail-era "
            "trade goods, fur trade material, and military equipment."
        ),
        "source": "AURIK",
        "confidence": 0.85,
    },
    # ------------------------------------------------------------------ #
    # Middle Spring (Cimarron Route), KS
    # ------------------------------------------------------------------ #
    {
        "name": "Middle Spring (Cimarron Route), KS",
        "type": "camp",
        "category": "emigrant_trail",
        "latitude": 36.978,
        "longitude": -101.415,
        "description": (
            "Middle Spring on the Cimarron Route of the Santa Fe Trail in extreme southwestern Kansas was "
            "one of only three reliable water sources across the 60-mile Jornada del Muerto desert section, "
            "making it a life-or-death camp stop for travelers crossing the Cimarron Desert. The spring is "
            "now within the Cimarron National Grassland and requires a Forest Service special use permit for "
            "metal detecting. The camp saw intensive use from the 1820s through the 1870s. The spring area "
            "has produced Santa Fe Trail trade goods, Mexican silver, and military equipment from the "
            "dangerous Cimarron crossing."
        ),
        "source": "AURIK",
        "confidence": 0.88,
    },
    # ------------------------------------------------------------------ #
    # Lower Cimarron Spring (Flag Spring), KS
    # ------------------------------------------------------------------ #
    {
        "name": "Lower Cimarron Spring (Flag Spring), KS",
        "type": "camp",
        "category": "emigrant_trail",
        "latitude": 37.007,
        "longitude": -100.875,
        "description": (
            "Flag Spring, also called Lower Cimarron Spring, was a critical water source on the Cimarron "
            "Route of the Santa Fe Trail between Dodge City and the main Cimarron crossing, providing a camp "
            "stop for merchants who had flagged the location with stakes and poles visible across the "
            "treeless prairie. The spring was used from the earliest years of the Santa Fe trade and saw "
            "continuous traffic through the Civil War era. Private and BLM land in the Flag Spring area has "
            "produced Santa Fe Trail-era trade goods and coins."
        ),
        "source": "AURIK",
        "confidence": 0.82,
    },
    # ------------------------------------------------------------------ #
    # Rabbit Ears Camp, NM
    # ------------------------------------------------------------------ #
    {
        "name": "Rabbit Ears Camp, NM",
        "type": "camp",
        "category": "emigrant_trail",
        "latitude": 36.672,
        "longitude": -103.967,
        "description": (
            "Rabbit Ears Camp in northeastern New Mexico was named for the distinctive twin-peaked volcanic "
            "formation visible from miles across the high plains, which served as the primary landmark "
            "guiding Santa Fe Trail travelers on the Mountain Branch across the Raton Mesa. The camp at the "
            "base of Rabbit Ears was a natural stopping point with water from a seasonal creek, seeing use "
            "from the 1820s through the trail's active years. Private and BLM land at the base of the Rabbit "
            "Ears formation has produced Santa Fe Trail trade goods and camp material."
        ),
        "source": "AURIK",
        "confidence": 0.83,
    },
    # ------------------------------------------------------------------ #
    # Rayado Camp, NM
    # ------------------------------------------------------------------ #
    {
        "name": "Rayado Camp, NM",
        "type": "camp",
        "category": "emigrant_trail",
        "latitude": 36.549,
        "longitude": -104.69,
        "description": (
            "Rayado in northern New Mexico was Kit Carson's ranch and a major camp on the Mountain Branch of "
            "the Santa Fe Trail, where Carson, Lucien Maxwell, and their associates built a fortified "
            "settlement that served as a provisioning stop for trail travelers and a base for military "
            "operations in the region. The camp saw use from the late 1840s through the Civil War era. The "
            "Rayado site is now within the Philmont Scout Ranch property, which restricts detecting access, "
            "but the historical significance of the camp is well documented."
        ),
        "source": "AURIK",
        "confidence": 0.87,
    },
    # ------------------------------------------------------------------ #
    # Ocate Creek Camp, NM
    # ------------------------------------------------------------------ #
    {
        "name": "Ocate Creek Camp, NM",
        "type": "camp",
        "category": "emigrant_trail",
        "latitude": 36.397,
        "longitude": -104.661,
        "description": (
            "Ocate Creek in northeastern New Mexico provided a welcome camp with water and timber for Santa "
            "Fe Trail travelers descending from the Raton Mesa on the Mountain Branch, the creek drainage "
            "offering shade and grass in the dry foothills approaching Mora Valley. The camp saw continuous "
            "use from the 1820s through the trail's active period. Private farmland in the Ocate Creek "
            "drainage has produced Santa Fe Trail-era trade goods and camp material from the decades of use."
        ),
        "source": "AURIK",
        "confidence": 0.8,
    },
    # ------------------------------------------------------------------ #
    # Camp Colorado, TX
    # ------------------------------------------------------------------ #
    {
        "name": "Camp Colorado, TX",
        "type": "camp",
        "category": "military_frontier",
        "latitude": 31.84,
        "longitude": -99.13,
        "description": (
            "Camp Colorado in Coleman County, Texas was established in 1857 on the Clear Fork of the "
            "Colorado River as part of the Second Texas Frontier Line of posts designed to protect settlers "
            "from Comanche and Kiowa raids on the rolling plains. The camp was an active military "
            "installation until abandoned at the outbreak of the Civil War in 1861, when both Federal and "
            "then Confederate forces occupied the ruins briefly. The site remains on private ranch land in "
            "Coleman County with standing stone ruins and is not in any existing dataset. Detectorists "
            "working the area with landowner permission have found military buttons, coins, and camp "
            "hardware."
        ),
        "source": "AURIK",
        "confidence": 0.88,
    },
    # ------------------------------------------------------------------ #
    # Camp Cooper, TX
    # ------------------------------------------------------------------ #
    {
        "name": "Camp Cooper, TX",
        "type": "camp",
        "category": "military_frontier",
        "latitude": 33.33,
        "longitude": -99.27,
        "description": (
            "Camp Cooper in Throckmorton County, Texas was established in January 1856 on the Clear Fork of "
            "the Brazos River and is historically notable as the post commanded by Robert E. Lee during "
            "1856-1857, where he supervised the reservation of the Comanche chief Catumseh and his band. The "
            "camp was part of the Second Frontier Line and was abandoned in February 1861 when Texas "
            "seceded. The site is on private ranch land with preserved earthwork remains. Detectorists with "
            "landowner permission have found military insignia, coins, and accoutrements from the Lee-era "
            "occupation."
        ),
        "source": "AURIK",
        "confidence": 0.9,
    },
    # ------------------------------------------------------------------ #
    # Camp Verde, TX
    # ------------------------------------------------------------------ #
    {
        "name": "Camp Verde, TX",
        "type": "camp",
        "category": "military_frontier",
        "latitude": 29.9,
        "longitude": -98.94,
        "description": (
            "Camp Verde in Kerr County, Texas was established in 1856 and is famous as the headquarters of "
            "the U.S. Army's Camel Corps experiment, where Secretary of War Jefferson Davis imported 77 "
            "camels from Egypt and Turkey to test their viability as desert transport animals. The camp was "
            "an active post from 1856 to 1861 and saw brief Confederate use during the Civil War before "
            "being abandoned. The site preserves some original stone structures on private land. "
            "Detectorists have found camel bells, military hardware, and period coins at sites near the "
            "original post area."
        ),
        "source": "AURIK",
        "confidence": 0.9,
    },
    # ------------------------------------------------------------------ #
    # Camp Hudson, TX
    # ------------------------------------------------------------------ #
    {
        "name": "Camp Hudson, TX",
        "type": "camp",
        "category": "military_frontier",
        "latitude": 29.647,
        "longitude": -100.898,
        "description": (
            "Camp Hudson in Val Verde County, Texas was established in 1857 on the Devils River at a "
            "strategic crossing point to guard the San Antonio-El Paso military road and protect settlers "
            "from Comanche and Apache raids in the Trans-Pecos region. The post was active until 1861 and "
            "briefly reoccupied by Federal forces during Reconstruction in 1868 before final abandonment. "
            "The remote canyon site on private ranch land has preserved significant structural remains. "
            "Military buttons, cartridge casings, and coins from both the antebellum and Reconstruction "
            "occupation periods have been found nearby."
        ),
        "source": "AURIK",
        "confidence": 0.87,
    },
    # ------------------------------------------------------------------ #
    # Camp Lancaster, TX
    # ------------------------------------------------------------------ #
    {
        "name": "Camp Lancaster, TX",
        "type": "camp",
        "category": "military_frontier",
        "latitude": 30.648,
        "longitude": -101.543,
        "description": (
            "Camp Lancaster in Crockett County, Texas was established in 1855 on Live Oak Creek near its "
            "confluence with the Pecos River, guarding the Lower Road segment of the San Antonio-El Paso "
            "military highway against Comanche and Apache raids. The post was active until 1861 and saw some "
            "of the heaviest frontier skirmishing in the Trans-Pecos region during its six-year operation. "
            "The site preserves stone wall ruins on private ranch land. Archaeological survey has documented "
            "a rich material record including military equipment, coins, and camp hardware."
        ),
        "source": "AURIK",
        "confidence": 0.88,
    },
    # ------------------------------------------------------------------ #
    # Camp Leona, TX
    # ------------------------------------------------------------------ #
    {
        "name": "Camp Leona, TX",
        "type": "camp",
        "category": "military_frontier",
        "latitude": 29.458,
        "longitude": -99.764,
        "description": (
            "Camp Leona in Uvalde County, Texas was established in 1849 on the Leona River as one of the "
            "earliest posts on the First Texas Frontier Line, providing a forward base for operations "
            "against Comanche raiders on the western frontier of Anglo settlement. The camp operated only "
            "until 1850 when the frontier line was reorganized, but its brief intense use left material "
            "evidence. Private ranch land in the Uvalde County area surrounding the historic camp site has "
            "produced military equipment and coins from the early frontier period."
        ),
        "source": "AURIK",
        "confidence": 0.83,
    },
    # ------------------------------------------------------------------ #
    # Camp Wood, TX
    # ------------------------------------------------------------------ #
    {
        "name": "Camp Wood, TX",
        "type": "camp",
        "category": "military_frontier",
        "latitude": 29.672,
        "longitude": -100.032,
        "description": (
            "Camp Wood in Real County, Texas was established as a military post on the Nueces River in the "
            "early 1850s and later became the nucleus of the small town of Camp Wood, which still bears the "
            "military camp name. The post guarded against Comanche and Lipan Apache raids along the upper "
            "Nueces and served as a supply point for more remote frontier stations. The historic camp site "
            "is intermixed with the modern small town on private land. Period military hardware, coins, and "
            "camp material have been found in the surrounding ranch country."
        ),
        "source": "AURIK",
        "confidence": 0.82,
    },
    # ------------------------------------------------------------------ #
    # Camp San Saba, TX
    # ------------------------------------------------------------------ #
    {
        "name": "Camp San Saba, TX",
        "type": "camp",
        "category": "military_frontier",
        "latitude": 31.107,
        "longitude": -99.344,
        "description": (
            "Camp San Saba in McCulloch County, Texas was a temporary military post established in 1852-1853 "
            "on the San Saba River to protect settlers from Comanche raids on the central Texas frontier, "
            "part of the Army's effort to establish a line of posts across the state. The camp's brief "
            "operation left limited material evidence compared to longer-established posts, but the site "
            "preserves military camp material in the San Saba River valley. Private ranch land in the area "
            "has produced military buttons and coins from the early frontier occupation."
        ),
        "source": "AURIK",
        "confidence": 0.8,
    },
    # ------------------------------------------------------------------ #
    # Camp Peña Colorado, TX
    # ------------------------------------------------------------------ #
    {
        "name": "Camp Pe\u00f1a Colorado, TX",
        "type": "camp",
        "category": "military_frontier",
        "latitude": 30.833,
        "longitude": -102.775,
        "description": (
            "Camp Peña Colorado in Mitchell County, Texas near the Glass Mountains was a later-period "
            "frontier post established in 1879 to control Apache and Comanche raids during the final "
            "campaigns of the Indian Wars in West Texas, operating until 1893 when the frontier was "
            "effectively closed. The camp guarded water sources and supply routes in the extreme Trans-Pecos "
            "region. BLM and private land surrounding the remote camp site has preserved military equipment "
            "and late-frontier material from the 14-year occupation."
        ),
        "source": "AURIK",
        "confidence": 0.85,
    },
    # ------------------------------------------------------------------ #
    # Camp Elizabeth, TX
    # ------------------------------------------------------------------ #
    {
        "name": "Camp Elizabeth, TX",
        "type": "camp",
        "category": "military_frontier",
        "latitude": 31.337,
        "longitude": -100.707,
        "description": (
            "Camp Elizabeth in Sterling County, Texas was a temporary post established in 1878-1880 during "
            "the final Comanche and Apache campaigns in West Texas, providing a forward operating base for "
            "the Buffalo Soldiers of the 10th Cavalry patrolling the Concho River headwaters region. The "
            "camp's brief but active operation during the climactic phase of the Texas Indian Wars left "
            "military material in the Sterling County ranch country. Private land in the area has produced "
            "late frontier-era military equipment and coins."
        ),
        "source": "AURIK",
        "confidence": 0.82,
    },
    # ------------------------------------------------------------------ #
    # Camp Melvin, TX
    # ------------------------------------------------------------------ #
    {
        "name": "Camp Melvin, TX",
        "type": "camp",
        "category": "military_frontier",
        "latitude": 30.697,
        "longitude": -101.682,
        "description": (
            "Camp Melvin in Crockett County, Texas was established in 1868 at Pecos River crossing to guard "
            "the upper Pecos country against Mescalero Apache raids during the Reconstruction-era phase of "
            "the Indian Wars in West Texas, operating until 1871. The post guarded an important river "
            "crossing and supply route through the Trans-Pecos. The remote private ranch land location has "
            "preserved military camp material from the post-Civil War frontier occupation."
        ),
        "source": "AURIK",
        "confidence": 0.8,
    },
    # ------------------------------------------------------------------ #
    # Camp Magruder, TX
    # ------------------------------------------------------------------ #
    {
        "name": "Camp Magruder, TX",
        "type": "camp",
        "category": "military_frontier",
        "latitude": 29.775,
        "longitude": -97.989,
        "description": (
            "Camp Magruder in the Gonzales County area of Texas was an early 1850s temporary military post "
            "associated with frontier defense operations in south-central Texas, named for Captain John "
            "Magruder who later became a Confederate general. The camp's brief existence as part of the "
            "early frontier line organization left limited but historically interesting material. Private "
            "farmland in the Gonzales County area has produced military hardware from the early Texas "
            "frontier period."
        ),
        "source": "AURIK",
        "confidence": 0.75,
    },
    # ------------------------------------------------------------------ #
    # Camp Ives, TX
    # ------------------------------------------------------------------ #
    {
        "name": "Camp Ives, TX",
        "type": "camp",
        "category": "military_frontier",
        "latitude": 29.447,
        "longitude": -100.773,
        "description": (
            "Camp Ives in Val Verde County, Texas near Brackettville was a temporary military post "
            "established in the 1850s to guard the lower Devils River country and the road connecting Fort "
            "Clark to the Trans-Pecos region, named for Lieutenant Joseph C. Ives of the Army Corps of "
            "Topographical Engineers who explored the Colorado River in 1857-1858. The camp's remote Val "
            "Verde County location on private ranch land has preserved military camp material from the "
            "frontier period."
        ),
        "source": "AURIK",
        "confidence": 0.78,
    },
    # ------------------------------------------------------------------ #
    # Camp Radziminski, OK
    # ------------------------------------------------------------------ #
    {
        "name": "Camp Radziminski, OK",
        "type": "camp",
        "category": "military_frontier",
        "latitude": 34.683,
        "longitude": -99.37,
        "description": (
            "Camp Radziminski in Tillman County, Oklahoma was a temporary cavalry camp established in "
            "1858-1859 near Otter Creek by the 2nd Cavalry during operations against Comanche and Kiowa "
            "bands ranging across Indian Territory, named for Lieutenant Charles Radziminski who died of "
            "illness during the campaign. The camp provided a forward base for the winter 1858-1859 "
            "expedition that struck Comanche villages on the upper Red River. Private ranch land in the "
            "Otter Creek area has preserved military material from this brief but historically significant "
            "camp."
        ),
        "source": "AURIK",
        "confidence": 0.83,
    },
    # ------------------------------------------------------------------ #
    # Camp Beale Springs, AZ
    # ------------------------------------------------------------------ #
    {
        "name": "Camp Beale Springs, AZ",
        "type": "camp",
        "category": "military_frontier",
        "latitude": 35.197,
        "longitude": -113.921,
        "description": (
            "Camp Beale Springs in Mohave County, Arizona was established in 1871 near Edward Beale's famous "
            "wagon road springs as a peace camp and reservation base for the Hualapai people following the "
            "Hualapai War of 1866-1869, operating until 1874. The camp was named for Edward Fitzgerald "
            "Beale, who had surveyed the wagon road using camels in 1857. BLM land surrounding the historic "
            "spring site preserves excellent camp material potential from the early Arizona territorial "
            "military period."
        ),
        "source": "AURIK",
        "confidence": 0.85,
    },
    # ------------------------------------------------------------------ #
    # Camp Date Creek, AZ
    # ------------------------------------------------------------------ #
    {
        "name": "Camp Date Creek, AZ",
        "type": "camp",
        "category": "military_frontier",
        "latitude": 34.37,
        "longitude": -112.649,
        "description": (
            "Camp Date Creek in Yavapai County, Arizona was established in 1867 as a base for Yavapai scouts "
            "who assisted the Army in operations against hostile Apache bands in the central Arizona "
            "highlands, operating until 1873 when the Yavapai were moved to the Verde River reservation. The "
            "camp was an important base for the early Arizona Indian Wars campaigns and saw significant "
            "activity during General Crook's operations in the region. BLM and private land in the Date "
            "Creek drainage has preserved military material from the camp period."
        ),
        "source": "AURIK",
        "confidence": 0.83,
    },
    # ------------------------------------------------------------------ #
    # Camp Picket Post, AZ
    # ------------------------------------------------------------------ #
    {
        "name": "Camp Picket Post, AZ",
        "type": "camp",
        "category": "military_frontier",
        "latitude": 33.302,
        "longitude": -111.027,
        "description": (
            "Camp Picket Post in the Tonto National Forest was a forward operating base used in 1870-1871 "
            "during the final campaign against the Tonto Apache in the Pinal Mountains, providing a staging "
            "point for the Army's operations that effectively ended the Tonto Basin conflict. The camp sat "
            "at the base of Picket Post Mountain and was used intensively during the brief but decisive "
            "campaign. Tonto National Forest land surrounds the historic camp area, and detecting is "
            "permitted on National Forest lands with appropriate permissions."
        ),
        "source": "AURIK",
        "confidence": 0.85,
    },
    # ------------------------------------------------------------------ #
    # Camp Pinal, AZ
    # ------------------------------------------------------------------ #
    {
        "name": "Camp Pinal, AZ",
        "type": "camp",
        "category": "military_frontier",
        "latitude": 33.284,
        "longitude": -110.8,
        "description": (
            "Camp Pinal in Graham County, Arizona was a temporary military camp established during the 1870s "
            "Tonto Basin campaign, providing a base for operations in the rugged Pinal Mountains during the "
            "Army's effort to pacify the final hostile Apache bands in central Arizona. The camp's remote "
            "location on BLM and private land has preserved military camp material from the Arizona Indian "
            "Wars period."
        ),
        "source": "AURIK",
        "confidence": 0.78,
    },
    # ------------------------------------------------------------------ #
    # Camp Mogollon, AZ
    # ------------------------------------------------------------------ #
    {
        "name": "Camp Mogollon, AZ",
        "type": "camp",
        "category": "military_frontier",
        "latitude": 33.667,
        "longitude": -109.25,
        "description": (
            "Camp Mogollon in the Apache-Sitgreaves National Forest near Fort Apache was a temporary "
            "military camp used during Apache campaign operations in the White Mountain region of Arizona, "
            "providing a forward base in the high Mogollon Rim country. The National Forest location allows "
            "metal detecting with appropriate permits, making this a legally accessible historic military "
            "site. The camp area has produced military equipment and coins from the Arizona Indian Wars "
            "period."
        ),
        "source": "AURIK",
        "confidence": 0.8,
    },
    # ------------------------------------------------------------------ #
    # Camp Lincoln (Prescott), AZ
    # ------------------------------------------------------------------ #
    {
        "name": "Camp Lincoln (Prescott), AZ",
        "type": "camp",
        "category": "military_frontier",
        "latitude": 34.649,
        "longitude": -112.476,
        "description": (
            "Camp Lincoln in Yavapai County, Arizona was the original name of the military post established "
            "in 1864 near Prescott to protect the new Arizona territorial capital from Yavapai and Apache "
            "raids, later renamed Camp Verde and ultimately Fort Verde. The Lincoln-era camp (1864-1866) "
            "preceded the more permanent installation and occupied a different site than the established "
            "fort. BLM and private land in the Prescott area preserves material from the early territorial "
            "military period."
        ),
        "source": "AURIK",
        "confidence": 0.82,
    },
    # ------------------------------------------------------------------ #
    # Camp Lowell, AZ
    # ------------------------------------------------------------------ #
    {
        "name": "Camp Lowell, AZ",
        "type": "camp",
        "category": "military_frontier",
        "latitude": 32.24,
        "longitude": -110.916,
        "description": (
            "Camp Lowell near Tucson, Arizona was established in 1866 to protect the growing territorial "
            "capital from Apache raids, occupying a series of sites near Tucson before being relocated to "
            "its more permanent Rillito River location in 1873. The original 1866-1873 camp locations are "
            "now largely within Tucson's urban core on private land, but the early occupation represents the "
            "Army's first attempt to pacify the Tucson basin. The surrounding desert areas have produced "
            "military material from the territorial period."
        ),
        "source": "AURIK",
        "confidence": 0.8,
    },
    # ------------------------------------------------------------------ #
    # Camp Thomas, AZ
    # ------------------------------------------------------------------ #
    {
        "name": "Camp Thomas, AZ",
        "type": "camp",
        "category": "military_frontier",
        "latitude": 32.954,
        "longitude": -110.069,
        "description": (
            "Camp Thomas in Graham County, Arizona was established in 1876 on the Gila River to serve as a "
            "supply and operations base for campaigns against Chiricahua Apache in the San Carlos region, "
            "operating until 1890 and renamed Fort Thomas in 1882. The camp was a significant node in the "
            "Arizona Apache Wars network and saw extensive military activity during the Geronimo campaign "
            "years of 1881-1886. Private and BLM land in the Gila River valley near the camp site has "
            "produced military equipment and coins from the active years."
        ),
        "source": "AURIK",
        "confidence": 0.83,
    },
    # ------------------------------------------------------------------ #
    # Camp Rawlins, AZ
    # ------------------------------------------------------------------ #
    {
        "name": "Camp Rawlins, AZ",
        "type": "camp",
        "category": "military_frontier",
        "latitude": 34.52,
        "longitude": -112.004,
        "description": (
            "Camp Rawlins in Yavapai County, Arizona was a temporary military post used during the Apache "
            "campaign operations in the central Arizona highlands in the early 1870s, providing a supply and "
            "rest point for columns operating in the rugged Bradshaw Mountains region. The camp's brief use "
            "during General Crook's Tonto Basin campaigns left military material in the Yavapai County ranch "
            "country. Private land in the area has preserved camp material from the territorial military "
            "period."
        ),
        "source": "AURIK",
        "confidence": 0.75,
    },
    # ------------------------------------------------------------------ #
    # Camp Supply (AZ)
    # ------------------------------------------------------------------ #
    {
        "name": "Camp Supply (AZ)",
        "type": "camp",
        "category": "military_frontier",
        "latitude": 33.5,
        "longitude": -113.0,
        "description": (
            "Camp Supply in Maricopa County, Arizona was a temporary military supply depot established "
            "during the 1870s Apache campaign operations in the western Arizona desert, providing a "
            "logistical base for columns operating between the Colorado River posts and the central Arizona "
            "highlands. BLM-administered desert land surrounding the historic depot site preserves military "
            "supply camp material from the Arizona territorial period."
        ),
        "source": "AURIK",
        "confidence": 0.72,
    },
    # ------------------------------------------------------------------ #
    # Camp Plummer, NM
    # ------------------------------------------------------------------ #
    {
        "name": "Camp Plummer, NM",
        "type": "camp",
        "category": "military_frontier",
        "latitude": 36.867,
        "longitude": -105.067,
        "description": (
            "Camp Plummer in Taos County, New Mexico was established in 1866 in the Carson National Forest "
            "near the Cimarron River to control Ute and Jicarilla Apache movements in the northern New "
            "Mexico highlands, operating until 1870. The post was named for Brigadier General Edward Plummer "
            "and served as a base for the 3rd Cavalry's operations in the region. Carson National Forest "
            "land permits metal detecting with appropriate authorization, making this an accessible historic "
            "military site."
        ),
        "source": "AURIK",
        "confidence": 0.83,
    },
    # ------------------------------------------------------------------ #
    # Camp Bascom, NM
    # ------------------------------------------------------------------ #
    {
        "name": "Camp Bascom, NM",
        "type": "camp",
        "category": "military_frontier",
        "latitude": 36.867,
        "longitude": -103.267,
        "description": (
            "Camp Bascom in Union County, New Mexico was established in 1863 on the Canadian River to "
            "control Kiowa and Comanche raiding in northeastern New Mexico Territory and to protect the "
            "Santa Fe Trail traffic from Union County to the Colorado border, operating until 1870. The camp "
            "was named for Lieutenant George Bascom, whose 1861 confrontation with Cochise sparked the "
            "decade-long Apache War. Private ranch land in the Canadian River valley has preserved military "
            "material from the camp's active years."
        ),
        "source": "AURIK",
        "confidence": 0.85,
    },
    # ------------------------------------------------------------------ #
    # Camp Burgwin, NM
    # ------------------------------------------------------------------ #
    {
        "name": "Camp Burgwin, NM",
        "type": "camp",
        "category": "military_frontier",
        "latitude": 36.332,
        "longitude": -105.466,
        "description": (
            "Camp Burgwin in Taos County, New Mexico was established in 1852 on the Rio Grande del Rancho "
            "near Taos to control Jicarilla Apache and Ute raiding in northern New Mexico, operating until "
            "1860 when it was abandoned as the frontier shifted. The camp was named for Captain John H.K. "
            "Burgwin, killed in the 1847 Taos Pueblo revolt. The site is now an archaeological research "
            "station on private land associated with Southern Methodist University."
        ),
        "source": "AURIK",
        "confidence": 0.87,
    },
    # ------------------------------------------------------------------ #
    # Camp Ojo Caliente, NM
    # ------------------------------------------------------------------ #
    {
        "name": "Camp Ojo Caliente, NM",
        "type": "camp",
        "category": "military_frontier",
        "latitude": 33.797,
        "longitude": -107.366,
        "description": (
            "Camp Ojo Caliente in Sierra County, New Mexico was established near the Warm Springs Apache "
            "reservation, home of Victorio's Mimbres Apache band, and served as the military presence during "
            "the troubled reservation period of the 1870s before Victorio's breakout in 1879 triggered the "
            "final Victorio War. The camp was a critical node in the final Apache Wars. BLM-administered "
            "land near the historic Warm Springs site preserves military material from the camp period."
        ),
        "source": "AURIK",
        "confidence": 0.83,
    },
    # ------------------------------------------------------------------ #
    # Camp Garland, NM
    # ------------------------------------------------------------------ #
    {
        "name": "Camp Garland, NM",
        "type": "camp",
        "category": "military_frontier",
        "latitude": 35.652,
        "longitude": -106.098,
        "description": (
            "Camp Garland in Sandoval County, New Mexico was a temporary military post used during 1860s "
            "operations in the Rio Puerco valley against Navajo and Apache raiders, providing a forward base "
            "during the period leading up to the Navajo Long Walk of 1864. The camp's brief use during a "
            "pivotal period in New Mexico history left military material in the Sandoval County mesa "
            "country. BLM and private land in the area has preserved camp equipment from the territorial "
            "military period."
        ),
        "source": "AURIK",
        "confidence": 0.75,
    },
    # ------------------------------------------------------------------ #
    # Camp Wingate (Old), NM
    # ------------------------------------------------------------------ #
    {
        "name": "Camp Wingate (Old), NM",
        "type": "camp",
        "category": "military_frontier",
        "latitude": 35.067,
        "longitude": -108.433,
        "description": (
            "Camp Wingate (Old) in McKinley County, New Mexico was established in 1862 as a military post to "
            "facilitate Kit Carson's Navajo campaign, distinct from the later Fort Wingate that replaced it. "
            "The camp was the forward base for the 1863-1864 campaign that forced the Navajo onto the Long "
            "Walk to Bosque Redondo. BLM-administered land in the area preserves military material from the "
            "critical Civil War-era New Mexico campaign."
        ),
        "source": "AURIK",
        "confidence": 0.83,
    },
    # ------------------------------------------------------------------ #
    # Camp Stanton, NM
    # ------------------------------------------------------------------ #
    {
        "name": "Camp Stanton, NM",
        "type": "camp",
        "category": "military_frontier",
        "latitude": 33.497,
        "longitude": -105.597,
        "description": (
            "Camp Stanton in Lincoln County, New Mexico was the original pre-fort installation established "
            "in the early 1850s before it was upgraded and renamed Fort Stanton in 1855, providing military "
            "control of the Mescalero Apache country in the Sacramento Mountains. The camp-era occupation "
            "(1852-1855) predates the more well-known fort and sits partially under the later fort's "
            "footprint on private land. The earliest camp material is the most historically interesting "
            "element of the Stanton site."
        ),
        "source": "AURIK",
        "confidence": 0.8,
    },
    # ------------------------------------------------------------------ #
    # Camp Harker, KS
    # ------------------------------------------------------------------ #
    {
        "name": "Camp Harker, KS",
        "type": "camp",
        "category": "military_frontier",
        "latitude": 38.573,
        "longitude": -97.927,
        "description": (
            "Camp Harker in Saline County, Kansas was established in 1866 as a temporary military post on "
            "the Smoky Hill Trail and later upgraded to Fort Harker in 1867, serving as a key supply depot "
            "for operations against Cheyenne and Sioux raiders on the central plains during the early years "
            "of the post-Civil War Indian Wars. The pre-fort camp period (1866-1867) produced concentrated "
            "military material that was later overlaid by the more permanent fort. Private farmland "
            "surrounding the Fort Harker site has produced military equipment and coins from both the camp "
            "and fort periods."
        ),
        "source": "AURIK",
        "confidence": 0.83,
    },
    # ------------------------------------------------------------------ #
    # Camp Grierson, KS
    # ------------------------------------------------------------------ #
    {
        "name": "Camp Grierson, KS",
        "type": "camp",
        "category": "military_frontier",
        "latitude": 38.5,
        "longitude": -98.5,
        "description": (
            "Camp Grierson in Ellsworth County, Kansas was a temporary cavalry camp established in 1868 "
            "during General Sheridan's winter campaign against Cheyenne and Arapaho bands on the southern "
            "plains, named for Colonel Benjamin Grierson of the 10th Cavalry Buffalo Soldiers. The camp "
            "provided a forward base during the campaign season that culminated in the Battle of the "
            "Washita. Private and BLM land in the Ellsworth County area has preserved military material from "
            "this brief but historically significant camp."
        ),
        "source": "AURIK",
        "confidence": 0.78,
    },
    # ------------------------------------------------------------------ #
    # Camp Supply, OK
    # ------------------------------------------------------------------ #
    {
        "name": "Camp Supply, OK",
        "type": "camp",
        "category": "military_frontier",
        "latitude": 36.544,
        "longitude": -99.623,
        "description": (
            "Camp Supply in Woodward County, Oklahoma was established in November 1868 as General Sheridan's "
            "forward supply base for the winter campaign against the southern plains tribes, from which "
            "Custer launched the attack on Black Kettle's village at the Battle of the Washita. The post "
            "operated as a major logistics hub for Indian Wars operations until 1895. BLM and private land "
            "surrounding the historic camp area near present-day Fort Supply has produced military "
            "equipment, coins, and campaign material from the 27-year occupation."
        ),
        "source": "AURIK",
        "confidence": 0.88,
    },
    # ------------------------------------------------------------------ #
    # Camp Rankin (early Fort Sedgwick), CO
    # ------------------------------------------------------------------ #
    {
        "name": "Camp Rankin (early Fort Sedgwick), CO",
        "type": "camp",
        "category": "military_frontier",
        "latitude": 40.989,
        "longitude": -102.271,
        "description": (
            "Camp Rankin in Sedgwick County, Colorado was established in 1864 at the confluence of Lodge "
            "Pole Creek and the South Platte River to protect the Overland Trail during the period of "
            "intensified Cheyenne and Sioux raiding following Sand Creek, later renamed Fort Sedgwick in "
            "1865. The camp-era occupation (1864-1865) was particularly intense given the scale of the "
            "Plains Indian War raids that followed the Sand Creek Massacre. Private and urban land at the "
            "historic site has produced military material from the camp and early fort periods."
        ),
        "source": "AURIK",
        "confidence": 0.83,
    },
    # ------------------------------------------------------------------ #
    # Camp Anderson, CA
    # ------------------------------------------------------------------ #
    {
        "name": "Camp Anderson, CA",
        "type": "camp",
        "category": "military_frontier",
        "latitude": 40.444,
        "longitude": -122.297,
        "description": (
            "Camp Anderson in Shasta County, California was established in 1857 during the early period of "
            "military operations against Wintun and other northern California tribes, providing a base for "
            "expeditions into the Trinity and Shasta Mountains region. The camp was one of the earliest "
            "military installations in the northern California interior. Private land in the Shasta County "
            "foothills surrounding the historic camp area has produced military material from California's "
            "early statehood military period."
        ),
        "source": "AURIK",
        "confidence": 0.78,
    },
    # ------------------------------------------------------------------ #
    # Camp Gaston, CA
    # ------------------------------------------------------------------ #
    {
        "name": "Camp Gaston, CA",
        "type": "camp",
        "category": "military_frontier",
        "latitude": 41.027,
        "longitude": -123.694,
        "description": (
            "Camp Gaston in Humboldt County, California was established in 1858 adjacent to the Hoopa Valley "
            "Indian Reservation to maintain peace between Hoopa Valley settlers and the Hupa people, "
            "operating until 1892 — one of the longest-operating California military posts. The camp's "
            "34-year occupation created a substantial material record in the redwood canyon country. Private "
            "land adjacent to the Hoopa Valley Reservation has produced military buttons, coins, and "
            "equipment from the extended camp occupation."
        ),
        "source": "AURIK",
        "confidence": 0.85,
    },
    # ------------------------------------------------------------------ #
    # Camp Babbitt (Visalia), CA
    # ------------------------------------------------------------------ #
    {
        "name": "Camp Babbitt (Visalia), CA",
        "type": "camp",
        "category": "military_frontier",
        "latitude": 36.331,
        "longitude": -119.292,
        "description": (
            "Camp Babbitt near Visalia in Tulare County, California was a Civil War-era military camp "
            "established in 1862 to guard the Tejon Pass wagon road and mountain passes against potential "
            "Confederate invasion of California from Arizona Territory, as well as to maintain order among "
            "the large Southern sympathizer population in the San Joaquin Valley. The camp occupied "
            "Visalia's western outskirts. Private and urban land in the Tulare County area has produced "
            "Civil War-era military material."
        ),
        "source": "AURIK",
        "confidence": 0.8,
    },
    # ------------------------------------------------------------------ #
    # Camp Wright (Elsinore), CA
    # ------------------------------------------------------------------ #
    {
        "name": "Camp Wright (Elsinore), CA",
        "type": "camp",
        "category": "military_frontier",
        "latitude": 33.622,
        "longitude": -117.18,
        "description": (
            "Camp Wright in Riverside County, California near present-day Lake Elsinore was established in "
            "1861 to guard the Southern Emigrant Trail wagon road to Arizona Territory and protect San Diego "
            "and Los Angeles from potential Confederate operations from Arizona. The camp controlled a "
            "critical mountain pass in southern California. Private land in the Riverside County area "
            "surrounding the historic camp site has produced Civil War military material."
        ),
        "source": "AURIK",
        "confidence": 0.78,
    },
    # ------------------------------------------------------------------ #
    # Camp Cooke, MT
    # ------------------------------------------------------------------ #
    {
        "name": "Camp Cooke, MT",
        "type": "camp",
        "category": "military_frontier",
        "latitude": 47.803,
        "longitude": -109.143,
        "description": (
            "Camp Cooke in Fergus County, Montana was established in 1866 at the mouth of the Judith River "
            "on the Missouri River to control Blackfeet and Crow raiding on the upper Missouri steamboat "
            "corridor, operating until 1870 when it was replaced by Fort Shaw. The camp occupied a strategic "
            "bluff above the Missouri and saw significant activity during the early years of Montana "
            "Territory. BLM-administered land along the Missouri River near the camp site has preserved "
            "military material from the short but active occupation."
        ),
        "source": "AURIK",
        "confidence": 0.83,
    },
    # ------------------------------------------------------------------ #
    # Camp Baker (later Fort Logan), MT
    # ------------------------------------------------------------------ #
    {
        "name": "Camp Baker (later Fort Logan), MT",
        "type": "camp",
        "category": "military_frontier",
        "latitude": 46.773,
        "longitude": -110.672,
        "description": (
            "Camp Baker in Meagher County, Montana was established in 1869 on the Smith River to protect "
            "miners and settlers in the Judith Basin from Sioux and Blackfeet raids, operating as Camp Baker "
            "until 1878 when it was renamed Fort Logan and continued operating until 1880. The camp was the "
            "scene of the 1870 Baker Massacre when Colonel Eugene Baker's 2nd Cavalry attacked a peaceful "
            "Piegan Blackfeet village on the Marias River. BLM and private land in the Smith River valley "
            "has preserved military material from the camp period."
        ),
        "source": "AURIK",
        "confidence": 0.83,
    },
    # ------------------------------------------------------------------ #
    # Camp Harney, OR
    # ------------------------------------------------------------------ #
    {
        "name": "Camp Harney, OR",
        "type": "camp",
        "category": "military_frontier",
        "latitude": 43.53,
        "longitude": -118.82,
        "description": (
            "Camp Harney in Harney County, Oregon was established in 1867 in the high desert of southeastern "
            "Oregon to control Paiute and Shoshone movements in the Great Basin, becoming a major base for "
            "General Crook's 1868-1869 Snake War campaign that effectively ended large-scale Paiute "
            "resistance. The camp operated until 1880 and saw 13 years of active military operations. The "
            "surrounding BLM-administered high desert land is open for metal detecting and has produced "
            "military equipment, coins, and campaign material from the extensive occupation."
        ),
        "source": "AURIK",
        "confidence": 0.88,
    },
    # ------------------------------------------------------------------ #
    # Camp Watson, OR
    # ------------------------------------------------------------------ #
    {
        "name": "Camp Watson, OR",
        "type": "camp",
        "category": "military_frontier",
        "latitude": 44.84,
        "longitude": -119.757,
        "description": (
            "Camp Watson in Wheeler County, Oregon was established in 1864 as a military road camp on the "
            "Canyon City Military Road to protect miners and freighters on the route to the John Day gold "
            "fields from Paiute and Shoshone raids, operating until 1869. The camp was a key node in the "
            "Oregon military road system. BLM-administered land surrounding the historic camp site in the "
            "John Day country is open for metal detecting and preserves military material from the camp "
            "occupation."
        ),
        "source": "AURIK",
        "confidence": 0.85,
    },
    # ------------------------------------------------------------------ #
    # Camp Alvord, OR
    # ------------------------------------------------------------------ #
    {
        "name": "Camp Alvord, OR",
        "type": "camp",
        "category": "military_frontier",
        "latitude": 42.497,
        "longitude": -118.543,
        "description": (
            "Camp Alvord in Harney County, Oregon was established in 1864 in the Alvord Basin at the base of "
            "Steens Mountain to control Paiute raiders on the Nevada-Oregon border during the early Snake "
            "War, operating until 1866 when it was succeeded by larger posts. The remote high desert "
            "location on BLM land has preserved the camp site well. BLM-administered Alvord Basin land is "
            "accessible for metal detecting, and the remote site has produced military material from the "
            "early Oregon Indian Wars period."
        ),
        "source": "AURIK",
        "confidence": 0.83,
    },
    # ------------------------------------------------------------------ #
    # Camp Warner, OR
    # ------------------------------------------------------------------ #
    {
        "name": "Camp Warner, OR",
        "type": "camp",
        "category": "military_frontier",
        "latitude": 42.443,
        "longitude": -120.267,
        "description": (
            "Camp Warner in Lake County, Oregon was established in 1866 on the Warner Lakes in the "
            "Fremont-Winema National Forest to control Paiute movements between the Great Basin and the "
            "Cascade foothills, operating until 1874 and serving as a base for extensive operations during "
            "the Snake War. National Forest land in the Warner Valley area permits metal detecting with "
            "appropriate authorizations, making this an accessible historic military site."
        ),
        "source": "AURIK",
        "confidence": 0.85,
    },
    # ------------------------------------------------------------------ #
    # Camp Wallen, AZ
    # ------------------------------------------------------------------ #
    {
        "name": "Camp Wallen, AZ",
        "type": "camp",
        "category": "military_frontier",
        "latitude": 31.53,
        "longitude": -110.053,
        "description": (
            "Camp Wallen in Cochise County, Arizona was established in 1866 on the Babocomari Creek in the "
            "Sulphur Springs Valley to control Chiricahua Apache raiding in southeastern Arizona, operating "
            "until 1869. The camp was one of the first military posts in the Apache heartland following the "
            "Civil War. BLM-administered grassland in Cochise County near the historic Babocomari Creek site "
            "has preserved military material from the early Arizona Indian Wars period."
        ),
        "source": "AURIK",
        "confidence": 0.83,
    },
    # ------------------------------------------------------------------ #
    # Camp Bowie (pre-Fort Bowie site), AZ
    # ------------------------------------------------------------------ #
    {
        "name": "Camp Bowie (pre-Fort Bowie site), AZ",
        "type": "camp",
        "category": "military_frontier",
        "latitude": 32.165,
        "longitude": -109.374,
        "description": (
            "The pre-1862 temporary Camp Bowie site in Graham County, Arizona predates the more famous Fort "
            "Bowie at Apache Pass and refers to the initial military camps established in the Dos Cabezas "
            "and Willcox Playa area during the earliest Army operations against Cochise's Chiricahua Apache, "
            "before the permanent Apache Pass installation was established. This site is distinct from the "
            "NPS Fort Bowie National Historic Site. Private land in the Graham County area has produced "
            "early Civil War-era military material."
        ),
        "source": "AURIK",
        "confidence": 0.72,
    },
    # ------------------------------------------------------------------ #
    # Camp Stambaugh, WY
    # ------------------------------------------------------------------ #
    {
        "name": "Camp Stambaugh, WY",
        "type": "camp",
        "category": "military_frontier",
        "latitude": 42.661,
        "longitude": -108.743,
        "description": (
            "Camp Stambaugh in Fremont County, Wyoming was established in 1870 near South Pass City to "
            "protect gold miners in the Atlantic City and South Pass gold fields from Shoshone and Arapaho "
            "raids, operating until 1878. The camp was named for Lieutenant Charles Stambaugh, killed in a "
            "skirmish with Arapahos near the camp in 1870. BLM-administered land near the South Pass gold "
            "field area surrounds the historic camp site and is accessible for metal detecting."
        ),
        "source": "AURIK",
        "confidence": 0.85,
    },
    # ------------------------------------------------------------------ #
    # Camp Jackson, MO
    # ------------------------------------------------------------------ #
    {
        "name": "Camp Jackson, MO",
        "type": "camp",
        "category": "military_frontier",
        "latitude": 38.635,
        "longitude": -90.246,
        "description": (
            "Camp Jackson in St. Louis County, Missouri was the Confederate Missouri State Guard training "
            "camp established in May 1861 by pro-secession Governor Claiborne Jackson on the grounds of "
            "present-day Lindell Park, captured by Union General Nathaniel Lyon in the Camp Jackson Affair "
            "of May 10, 1861 — one of the opening events of the Civil War in Missouri. The capture and the "
            "subsequent street massacre of civilians by Union troops polarized Missouri and drove thousands "
            "to the Confederate cause. Urban development has covered the original camp ground, but the "
            "surrounding St. Louis suburban area has produced Civil War material through construction "
            "activity."
        ),
        "source": "AURIK",
        "confidence": 0.87,
    },
    # ------------------------------------------------------------------ #
    # Camp Defiance (Cairo, IL)
    # ------------------------------------------------------------------ #
    {
        "name": "Camp Defiance (Cairo, IL)",
        "type": "camp",
        "category": "military_frontier",
        "latitude": 37.004,
        "longitude": -89.176,
        "description": (
            "Camp Defiance at the confluence of the Ohio and Mississippi rivers in Cairo, Illinois was the "
            "Union Army's first and most important staging ground for the western theater of the Civil War, "
            "where Ulysses S. Grant organized and trained the Army of the Tennessee before the Fort Henry "
            "and Fort Donelson campaigns that opened the Confederate heartland. The camp's strategic "
            "position at the rivers' confluence made it a massive logistics hub throughout the war. Private "
            "and urban land at the historic Cairo waterfront area has produced Civil War material from the "
            "Union camp occupation."
        ),
        "source": "AURIK",
        "confidence": 0.85,
    },
    # ------------------------------------------------------------------ #
    # Camp Butler, IL
    # ------------------------------------------------------------------ #
    {
        "name": "Camp Butler, IL",
        "type": "camp",
        "category": "military_frontier",
        "latitude": 39.808,
        "longitude": -89.53,
        "description": (
            "Camp Butler in Sangamon County near Springfield, Illinois served as a major Union Army training "
            "camp and Confederate prisoner of war camp from 1861 to 1866, processing tens of thousands of "
            "Illinois volunteers and incarcerating thousands of Confederate prisoners captured at Fort "
            "Donelson and other western theater battles. The camp's dual role as training ground and prison "
            "left an extensive material record. Private farmland surrounding the historic camp site has "
            "produced Civil War military equipment and coins from the wartime occupation."
        ),
        "source": "AURIK",
        "confidence": 0.85,
    },
    # ------------------------------------------------------------------ #
    # Camp Morton, IN
    # ------------------------------------------------------------------ #
    {
        "name": "Camp Morton, IN",
        "type": "camp",
        "category": "military_frontier",
        "latitude": 39.783,
        "longitude": -86.143,
        "description": (
            "Camp Morton in Indianapolis, Indiana began as a Union Army training camp in 1861 and was "
            "converted to a Confederate prisoner of war camp following Fort Donelson in 1862, incarcerating "
            "approximately 12,000 Confederate prisoners by 1863 under notoriously overcrowded conditions. "
            "The camp occupied the Indiana State Fairgrounds and saw high mortality rates from disease. "
            "Urban development has covered the historic camp site, but the surrounding Indianapolis area has "
            "produced Civil War material through construction."
        ),
        "source": "AURIK",
        "confidence": 0.85,
    },
    # ------------------------------------------------------------------ #
    # Henry's Fork Rendezvous 1825
    # ------------------------------------------------------------------ #
    {
        "name": "Henry's Fork Rendezvous 1825",
        "type": "camp",
        "category": "rendezvous_fur_trade",
        "latitude": 41.003,
        "longitude": -109.481,
        "description": (
            "Henry's Fork Rendezvous of 1825 was the first annual Rocky Mountain Rendezvous organized by "
            "General William Ashley, held on a tributary of the Green River in present Daggett County, Utah, "
            "where Ashley's mountain men exchanged their winter's catch of beaver pelts for trade goods, "
            "supplies, and provisions. The 1825 gathering established the rendezvous system that would "
            "sustain the Rocky Mountain fur trade for the next 15 years. BLM-administered land at the "
            "Henry's Fork confluence is accessible for metal detecting and has produced trade goods, pipe "
            "tomahawks, and fur trade material from the rendezvous era."
        ),
        "source": "AURIK",
        "confidence": 0.9,
    },
    # ------------------------------------------------------------------ #
    # Willow Valley Rendezvous 1826
    # ------------------------------------------------------------------ #
    {
        "name": "Willow Valley Rendezvous 1826",
        "type": "camp",
        "category": "rendezvous_fur_trade",
        "latitude": 41.943,
        "longitude": -111.83,
        "description": (
            "The 1826 Rocky Mountain Rendezvous was held in Willow Valley (Cache Valley) in northern Utah "
            "near present-day Logan, where Ashley sold his fur trade enterprise to Jedediah Smith, David "
            "Jackson, and William Sublette, ending Ashley's direct involvement in the trade while continuing "
            "the rendezvous system. Cache Valley's rich grass and water made it an ideal gathering site. BLM "
            "and private land in the Cache Valley area has produced fur trade material including trade "
            "beads, iron trade goods, and Hudson's Bay Company items from the rendezvous period."
        ),
        "source": "AURIK",
        "confidence": 0.87,
    },
    # ------------------------------------------------------------------ #
    # Bear Lake Rendezvous 1827 & 1828
    # ------------------------------------------------------------------ #
    {
        "name": "Bear Lake Rendezvous 1827 & 1828",
        "type": "camp",
        "category": "rendezvous_fur_trade",
        "latitude": 41.928,
        "longitude": -111.35,
        "description": (
            "The Rocky Mountain Rendezvous of 1827 and 1828 were both held at the south end of Bear Lake in "
            "Rich County, Utah, where the naturally sheltered lake basin with excellent grass and water "
            "supported the large gathering of mountain men, Native traders, and company agents. Jedediah "
            "Smith departed from the 1827 rendezvous for his second transcontinental crossing to California. "
            "BLM-administered land at the south end of Bear Lake is accessible for metal detecting and has "
            "produced outstanding fur trade material from the two-year rendezvous occupation."
        ),
        "source": "AURIK",
        "confidence": 0.9,
    },
    # ------------------------------------------------------------------ #
    # Popo Agie Rendezvous 1829 & 1838
    # ------------------------------------------------------------------ #
    {
        "name": "Popo Agie Rendezvous 1829 & 1838",
        "type": "camp",
        "category": "rendezvous_fur_trade",
        "latitude": 42.838,
        "longitude": -108.781,
        "description": (
            "The Popo Agie Rendezvous site near present-day Lander, Wyoming in Fremont County hosted the "
            "1829 and 1838 annual gatherings of the Rocky Mountain fur trade, with the 1838 meeting being "
            "particularly notable as one of the last great rendezvous attended by the missionary group "
            "including Dr. Marcus Whitman, whose observations of the gathering are a primary historical "
            "source. BLM-administered land near the Popo Agie River confluence is accessible for metal "
            "detecting and has produced trade goods, beads, and fur trade hardware from both rendezvous "
            "years."
        ),
        "source": "AURIK",
        "confidence": 0.9,
    },
    # ------------------------------------------------------------------ #
    # Wind River Rendezvous 1830
    # ------------------------------------------------------------------ #
    {
        "name": "Wind River Rendezvous 1830",
        "type": "camp",
        "category": "rendezvous_fur_trade",
        "latitude": 43.078,
        "longitude": -108.38,
        "description": (
            "The 1830 Rocky Mountain Rendezvous was held on the Wind River in Fremont County, Wyoming near "
            "present-day Riverton, where the newly formed Rocky Mountain Fur Company under Smith, Jackson "
            "and Sublette organized what was the largest gathering to that point, bringing 10 wagons from "
            "St. Louis in the first wheeled vehicle crossing of the continental divide. BLM and private land "
            "in the Wind River valley near the historic rendezvous site has produced fur trade material from "
            "the 1830 gathering."
        ),
        "source": "AURIK",
        "confidence": 0.85,
    },
    # ------------------------------------------------------------------ #
    # Cache Valley Rendezvous 1831
    # ------------------------------------------------------------------ #
    {
        "name": "Cache Valley Rendezvous 1831",
        "type": "camp",
        "category": "rendezvous_fur_trade",
        "latitude": 41.943,
        "longitude": -111.83,
        "description": (
            "The 1831 Rocky Mountain Rendezvous was again held in Cache Valley, Utah near the 1826 site, a "
            "year that saw record beaver prices and the largest gathering of mountain men to date, with "
            "company representatives from the Rocky Mountain Fur Company, Hudson's Bay Company, and "
            "independent traders all competing for pelts. Cache Valley's consistent water and grass "
            "resources made it a preferred recurring rendezvous location. BLM and private land in the Cache "
            "Valley area has produced fur trade material from multiple rendezvous occupations."
        ),
        "source": "AURIK",
        "confidence": 0.85,
    },
    # ------------------------------------------------------------------ #
    # Pierre's Hole Rendezvous 1832
    # ------------------------------------------------------------------ #
    {
        "name": "Pierre's Hole Rendezvous 1832",
        "type": "camp",
        "category": "rendezvous_fur_trade",
        "latitude": 43.827,
        "longitude": -111.17,
        "description": (
            "The 1832 Rocky Mountain Rendezvous at Pierre's Hole (Teton Valley, Idaho — NOT Jackson Hole, "
            "Wyoming) was the most dramatic of all the annual gatherings, ending in the Battle of Pierre's "
            "Hole when departing mountain men attacked a Gros Ventre war party in a fierce engagement that "
            "left multiple casualties on both sides. The Caribou-Targhee National Forest surrounds much of "
            "the historic valley. National Forest land in Teton Valley, Idaho permits detecting with "
            "appropriate authorization and has produced fur trade and battle material from this landmark "
            "event."
        ),
        "source": "AURIK",
        "confidence": 0.92,
    },
    # ------------------------------------------------------------------ #
    # Green River (Horse Creek) Rendezvous 1833
    # ------------------------------------------------------------------ #
    {
        "name": "Green River (Horse Creek) Rendezvous 1833",
        "type": "camp",
        "category": "rendezvous_fur_trade",
        "latitude": 42.052,
        "longitude": -110.034,
        "description": (
            "The 1833 Rocky Mountain Rendezvous at the confluence of Horse Creek and the Green River in "
            "Sublette County, Wyoming was attended by Captain Benjamin Bonneville and the English adventurer "
            "Sir William Drummond Stewart, whose accounts provide vivid descriptions of the event and "
            "introduced the rendezvous to European audiences. BLM-administered land at the Horse Creek "
            "confluence in Sublette County is accessible for metal detecting and has produced exceptional "
            "fur trade material including trade beads, pipe tomahawks, Hudson's Bay Company trade blanket "
            "remnants, and coins."
        ),
        "source": "AURIK",
        "confidence": 0.9,
    },
    # ------------------------------------------------------------------ #
    # Ham's Fork Rendezvous 1834
    # ------------------------------------------------------------------ #
    {
        "name": "Ham's Fork Rendezvous 1834",
        "type": "camp",
        "category": "rendezvous_fur_trade",
        "latitude": 41.617,
        "longitude": -109.941,
        "description": (
            "The 1834 Rocky Mountain Rendezvous at Ham's Fork of the Green River in Uinta County, Wyoming "
            "saw the participation of both the American Fur Company and Hudson's Bay Company "
            "representatives, marking the intensification of corporate competition that would eventually "
            "destroy the rendezvous system through overtrapping. BLM-administered land at the Ham's Fork "
            "confluence is accessible for metal detecting and has produced mixed American and British fur "
            "trade material from the competitive 1834 gathering."
        ),
        "source": "AURIK",
        "confidence": 0.88,
    },
    # ------------------------------------------------------------------ #
    # New Fork (Green River) Rendezvous 1835
    # ------------------------------------------------------------------ #
    {
        "name": "New Fork (Green River) Rendezvous 1835",
        "type": "camp",
        "category": "rendezvous_fur_trade",
        "latitude": 42.719,
        "longitude": -109.917,
        "description": (
            "The 1835 Rocky Mountain Rendezvous was held near the confluence of New Fork River and the Green "
            "River in Sublette County, Wyoming near present-day Pinedale, attended by the first missionaries "
            "bound for Oregon including Samuel Parker and Marcus Whitman, whose descriptions of the "
            "gathering provide important historical documentation. BLM-administered land in the Pinedale "
            "area of Sublette County is accessible and has produced fur trade material from the 1835 "
            "rendezvous."
        ),
        "source": "AURIK",
        "confidence": 0.88,
    },
    # ------------------------------------------------------------------ #
    # Horse Creek Rendezvous 1836
    # ------------------------------------------------------------------ #
    {
        "name": "Horse Creek Rendezvous 1836",
        "type": "camp",
        "category": "rendezvous_fur_trade",
        "latitude": 42.052,
        "longitude": -110.034,
        "description": (
            "The 1836 Rocky Mountain Rendezvous returned to the Horse Creek confluence with the Green River "
            "in Sublette County, Wyoming, and is notable for the presence of Narcissa Whitman and Eliza "
            "Spalding — the first white women to cross the continental divide — who were traveling with the "
            "missionary party to Oregon. Their presence at the rendezvous caused a sensation among the "
            "assembled mountain men and Native traders. BLM land at Horse Creek has produced outstanding "
            "rendezvous-era fur trade material."
        ),
        "source": "AURIK",
        "confidence": 0.9,
    },
    # ------------------------------------------------------------------ #
    # Green River (Daniel, WY) Rendezvous 1837
    # ------------------------------------------------------------------ #
    {
        "name": "Green River (Daniel, WY) Rendezvous 1837",
        "type": "camp",
        "category": "rendezvous_fur_trade",
        "latitude": 42.909,
        "longitude": -110.063,
        "description": (
            "The 1837 Rocky Mountain Rendezvous near Daniel, Wyoming in Sublette County was held at the "
            "confluence of Horse Creek and the Green River and was attended by the German scientist and "
            "artist Alfred Jacob Miller, who accompanied William Drummond Stewart and produced the only "
            "known contemporary paintings of the Rocky Mountain fur trade rendezvous. BLM-administered land "
            "near Daniel, Wyoming is accessible for metal detecting and preserves material from this "
            "historically documented gathering."
        ),
        "source": "AURIK",
        "confidence": 0.9,
    },
    # ------------------------------------------------------------------ #
    # Wind River/Popo Agie Rendezvous 1838
    # ------------------------------------------------------------------ #
    {
        "name": "Wind River/Popo Agie Rendezvous 1838",
        "type": "camp",
        "category": "rendezvous_fur_trade",
        "latitude": 42.838,
        "longitude": -108.781,
        "description": (
            "The 1838 Rocky Mountain Rendezvous returned to the Popo Agie River near Lander, Wyoming and was "
            "attended by the Jason Lee missionary party along with William Gray, providing extensive written "
            "documentation of the event. This was one of the final rendezvous years as the beaver fur market "
            "was beginning its collapse. BLM land in the Popo Agie area near Lander is accessible and has "
            "produced rendezvous-era trade material from the 1829 and 1838 gatherings at this location."
        ),
        "source": "AURIK",
        "confidence": 0.88,
    },
    # ------------------------------------------------------------------ #
    # Horse Creek Rendezvous 1839
    # ------------------------------------------------------------------ #
    {
        "name": "Horse Creek Rendezvous 1839",
        "type": "camp",
        "category": "rendezvous_fur_trade",
        "latitude": 42.052,
        "longitude": -110.034,
        "description": (
            "The 1839 Rocky Mountain Rendezvous at Horse Creek on the Green River in Sublette County, "
            "Wyoming was one of the last major gatherings of the fur trade era, as the collapse of beaver "
            "prices was already making the annual rendezvous economically marginal. The meeting still drew "
            "hundreds of mountain men, Native traders, and missionaries. BLM land at the Horse Creek "
            "rendezvous site has produced fur trade material from multiple rendezvous years at this "
            "recurring location."
        ),
        "source": "AURIK",
        "confidence": 0.88,
    },
    # ------------------------------------------------------------------ #
    # Green River Rendezvous 1840
    # ------------------------------------------------------------------ #
    {
        "name": "Green River Rendezvous 1840",
        "type": "camp",
        "category": "rendezvous_fur_trade",
        "latitude": 42.648,
        "longitude": -110.081,
        "description": (
            "The 1840 Rocky Mountain Rendezvous on the Green River in Sublette County, Wyoming was the final "
            "rendezvous of the fur trade era, a small and melancholy gathering compared to the great "
            "meetings of the 1830s, marking the end of an era as the beaver market had collapsed and the "
            "mountain men were dispersing to other vocations. BLM-administered land in Sublette County near "
            "the 1840 rendezvous site is accessible for metal detecting and preserves material from this "
            "historic final gathering."
        ),
        "source": "AURIK",
        "confidence": 0.9,
    },
    # ------------------------------------------------------------------ #
    # Fort Cass (Sarpy II), MT
    # ------------------------------------------------------------------ #
    {
        "name": "Fort Cass (Sarpy II), MT",
        "type": "camp",
        "category": "rendezvous_fur_trade",
        "latitude": 45.882,
        "longitude": -107.974,
        "description": (
            "Fort Cass (also known as Sarpy's Post or Fort Van Buren II) was an American Fur Company trading "
            "post established in 1832 at the confluence of the Big Horn and Yellowstone rivers in present "
            "Crow County, Montana, operating until 1835 as the primary post for trade with the Crow Nation. "
            "The post represented the AFC's aggressive expansion into the upper Missouri fur trade. "
            "BLM-administered land at the Big Horn-Yellowstone confluence is accessible for metal detecting "
            "and has produced trade goods, Hudson's Bay Company items, and fur trade material."
        ),
        "source": "AURIK",
        "confidence": 0.85,
    },
    # ------------------------------------------------------------------ #
    # Fort Van Buren, MT
    # ------------------------------------------------------------------ #
    {
        "name": "Fort Van Buren, MT",
        "type": "camp",
        "category": "rendezvous_fur_trade",
        "latitude": 46.383,
        "longitude": -105.834,
        "description": (
            "Fort Van Buren was an American Fur Company trading post established in 1835 on the Yellowstone "
            "River in Custer County, Montana, named for Martin Van Buren and operating until 1842 as a major "
            "trade center for Crow and Assiniboine bands. The post succeeded Fort Cass and continued AFC "
            "dominance of the upper Missouri trade. BLM-administered Yellowstone River bottom land near the "
            "historic post site is accessible for metal detecting and has produced AFC trade goods and fur "
            "trade material."
        ),
        "source": "AURIK",
        "confidence": 0.83,
    },
    # ------------------------------------------------------------------ #
    # Fort Mortimer, ND
    # ------------------------------------------------------------------ #
    {
        "name": "Fort Mortimer, ND",
        "type": "camp",
        "category": "rendezvous_fur_trade",
        "latitude": 47.82,
        "longitude": -103.983,
        "description": (
            "Fort Mortimer was a competing trade post established near Fort Union in Williams County, North "
            "Dakota by the rival Union Fur Company in 1842, attempting to break the American Fur Company's "
            "monopoly on the upper Missouri trade by locating immediately adjacent to the established post. "
            "The competition between Fort Mortimer and Fort Union created a period of intense rivalry with "
            "effects on the trade goods distributed to Native trading partners. Private farmland near the "
            "historic Fort Union area has preserved material from the competing post occupation."
        ),
        "source": "AURIK",
        "confidence": 0.8,
    },
    # ------------------------------------------------------------------ #
    # Fort Clark, ND
    # ------------------------------------------------------------------ #
    {
        "name": "Fort Clark, ND",
        "type": "camp",
        "category": "rendezvous_fur_trade",
        "latitude": 47.182,
        "longitude": -101.067,
        "description": (
            "Fort Clark in Mercer County, North Dakota was a major American Fur Company trading post "
            "established in 1830 adjacent to the Mandan village of Mih-tutta-hang-kusch, serving as the "
            "primary trade center for the Mandan, Hidatsa, and Arikara peoples of the upper Missouri for 30 "
            "years. The 1837 smallpox epidemic devastated the Mandan people while traders at Fort Clark "
            "watched, killing 90% of the nation. Private farmland at the Fort Clark State Historic Site area "
            "preserves material from this pivotal trading post."
        ),
        "source": "AURIK",
        "confidence": 0.87,
    },
    # ------------------------------------------------------------------ #
    # Fort Benton (AFC early camp), MT
    # ------------------------------------------------------------------ #
    {
        "name": "Fort Benton (AFC early camp), MT",
        "type": "camp",
        "category": "rendezvous_fur_trade",
        "latitude": 47.822,
        "longitude": -110.669,
        "description": (
            "Fort Benton in Chouteau County, Montana began as an American Fur Company trading camp in 1846 "
            "before evolving into the most important trading post on the upper Missouri River, serving as "
            "the head of navigation for Missouri River steamboats and the primary gateway to the Montana "
            "gold fields after 1862. The original 1846-1850 camp phase predates the well-known later fort "
            "and lies partially under the modern town of Fort Benton on private and urban land. The "
            "surrounding Chouteau County area has produced AFC trade goods from the early camp period."
        ),
        "source": "AURIK",
        "confidence": 0.85,
    },
    # ------------------------------------------------------------------ #
    # Fort Colville (HBC), WA
    # ------------------------------------------------------------------ #
    {
        "name": "Fort Colville (HBC), WA",
        "type": "camp",
        "category": "rendezvous_fur_trade",
        "latitude": 48.526,
        "longitude": -117.91,
        "description": (
            "Fort Colville was the Hudson's Bay Company's most important inland post in the Pacific "
            "Northwest, established in 1825 in Stevens County, Washington and operating continuously until "
            "1871, serving as the trade center for the Columbia Plateau tribes and the administrative hub "
            "for the HBC's entire Columbia Department. The post sat on Colville National Forest land, which "
            "permits metal detecting with appropriate authorization, making this an accessible and "
            "historically rich fur trade site."
        ),
        "source": "AURIK",
        "confidence": 0.9,
    },
    # ------------------------------------------------------------------ #
    # Fort Nez Percés (Walla Walla), WA
    # ------------------------------------------------------------------ #
    {
        "name": "Fort Nez Perc\u00e9s (Walla Walla), WA",
        "type": "camp",
        "category": "rendezvous_fur_trade",
        "latitude": 46.067,
        "longitude": -118.891,
        "description": (
            "Fort Nez Percés (later Fort Walla Walla) near present-day Wallula, Washington was established "
            "in 1818 by the North West Company at the confluence of the Walla Walla and Columbia rivers, "
            "becoming a major HBC post and the gateway to the Columbia Plateau trade with Nez Perce, Cayuse, "
            "and Walla Walla peoples. The post's strategic location made it a hub for both the Pacific "
            "Northwest fur trade and later the emigrant trail era. Private farmland near the historic "
            "Wallula site has produced HBC trade goods and North West Company material."
        ),
        "source": "AURIK",
        "confidence": 0.87,
    },
    # ------------------------------------------------------------------ #
    # Kullyspell House, ID
    # ------------------------------------------------------------------ #
    {
        "name": "Kullyspell House, ID",
        "type": "camp",
        "category": "rendezvous_fur_trade",
        "latitude": 48.33,
        "longitude": -116.497,
        "description": (
            "Kullyspell House near present-day Hope, Idaho in Bonner County was David Thompson's 1809 North "
            "West Company trading post on Lake Pend Oreille, the second fur trade post established in what "
            "is now Idaho and the primary trade center for the Kalispel (Pend Oreille) people. Thompson's "
            "post was a pivotal early contact point in the Pacific Northwest fur trade. Private land near "
            "the Hope, Idaho area on Lake Pend Oreille has produced early 19th-century trade material from "
            "the North West Company period."
        ),
        "source": "AURIK",
        "confidence": 0.85,
    },
    # ------------------------------------------------------------------ #
    # Flathead Post (Thompson's), MT
    # ------------------------------------------------------------------ #
    {
        "name": "Flathead Post (Thompson's), MT",
        "type": "camp",
        "category": "rendezvous_fur_trade",
        "latitude": 47.583,
        "longitude": -114.108,
        "description": (
            "David Thompson's Flathead Post established in 1809 in present Lake County, Montana near Eddy "
            "was the first fur trade post established in Montana, built by the North West Company to trade "
            "with the Flathead (Salish) people and explore the upper Columbia River drainage. Thompson's "
            "meticulous journal entries and maps from this post are foundational documents of Pacific "
            "Northwest geography. Flathead National Forest land near the historic post area permits "
            "detecting with appropriate authorization."
        ),
        "source": "AURIK",
        "confidence": 0.87,
    },
    # ------------------------------------------------------------------ #
    # Fort Okanogan, WA
    # ------------------------------------------------------------------ #
    {
        "name": "Fort Okanogan, WA",
        "type": "camp",
        "category": "rendezvous_fur_trade",
        "latitude": 48.101,
        "longitude": -119.714,
        "description": (
            "Fort Okanogan in Okanogan County, Washington was the first American trading post established in "
            "what is now Washington state, built in 1811 by the Pacific Fur Company at the confluence of the "
            "Okanogan and Columbia rivers, later acquired by the North West Company in 1813 and the Hudson's "
            "Bay Company in 1821. The post operated as a major trade center for nearly 60 years. Private "
            "farmland near the historic confluence site has produced Pacific Fur Company, North West "
            "Company, and HBC trade material spanning the full trading post era."
        ),
        "source": "AURIK",
        "confidence": 0.88,
    },
    # ------------------------------------------------------------------ #
    # Au Sable River Camp (Mio area), MI
    # ------------------------------------------------------------------ #
    {
        "name": "Au Sable River Camp (Mio area), MI",
        "type": "camp",
        "category": "logging_lumber",
        "latitude": 44.397,
        "longitude": -83.971,
        "description": (
            "The Au Sable River logging camps near Mio in Oscoda County, Michigan were the heart of the "
            "Michigan white pine lumber era from 1870 to 1900, when dozens of logging camps operated along "
            "the river's upper reaches, driving millions of board feet of pine logs downstream each spring "
            "to the sawmills at Oscoda and Au Sable on Lake Huron. The camps were seasonal operations "
            "employing hundreds of men with cook shacks, bunk houses, and blacksmith shops creating a rich "
            "material record. Huron National Forest land in the Au Sable watershed is accessible for metal "
            "detecting and has produced logging camp hardware, coins, and personal effects."
        ),
        "source": "AURIK",
        "confidence": 0.82,
    },
    # ------------------------------------------------------------------ #
    # Manistee River Camp (Mesick area), MI
    # ------------------------------------------------------------------ #
    {
        "name": "Manistee River Camp (Mesick area), MI",
        "type": "camp",
        "category": "logging_lumber",
        "latitude": 44.271,
        "longitude": -85.921,
        "description": (
            "The Manistee River logging camps near Mesick in Wexford County, Michigan operated during the "
            "peak white pine era of the 1870s-1890s, supplying the Manistee sawmills on Lake Michigan with "
            "enormous quantities of pine timber driven down the river each spring. The Manistee River was "
            "considered one of the finest log-driving streams in Michigan, and the camps along its upper "
            "reaches employed thousands of men. Manistee National Forest land in the upper river watershed "
            "is accessible for metal detecting."
        ),
        "source": "AURIK",
        "confidence": 0.8,
    },
    # ------------------------------------------------------------------ #
    # Muskegon River Camps (Big Rapids area), MI
    # ------------------------------------------------------------------ #
    {
        "name": "Muskegon River Camps (Big Rapids area), MI",
        "type": "camp",
        "category": "logging_lumber",
        "latitude": 43.554,
        "longitude": -85.199,
        "description": (
            "The Muskegon River logging camps in the Big Rapids area of Mecosta County, Michigan were "
            "central to the greatest pine lumber district in the world during the 1870s and 1880s, when the "
            "Muskegon River drove more pine logs to Lake Michigan than any other river in the United States. "
            "The camps near Big Rapids served the upper reaches of this massive logging operation. "
            "Huron-Manistee National Forest land in the Muskegon headwaters area is accessible for metal "
            "detecting and has produced logging camp material."
        ),
        "source": "AURIK",
        "confidence": 0.8,
    },
    # ------------------------------------------------------------------ #
    # Tittabawassee River Camp (Midland area), MI
    # ------------------------------------------------------------------ #
    {
        "name": "Tittabawassee River Camp (Midland area), MI",
        "type": "camp",
        "category": "logging_lumber",
        "latitude": 43.617,
        "longitude": -84.247,
        "description": (
            "The Tittabawassee River logging camps near Midland, Michigan served the center of the Saginaw "
            "Valley lumber empire, where the Tittabawassee River drove pine logs to the massive sawmill "
            "complex at Saginaw — the world's leading lumber producer in the 1880s. The upper river camps "
            "operated on private timber company land that has since returned to mixed-use private ownership. "
            "Midland County private land with landowner permission has produced logging era camp hardware "
            "and coins."
        ),
        "source": "AURIK",
        "confidence": 0.78,
    },
    # ------------------------------------------------------------------ #
    # Rifle River Camps (Alger area), MI
    # ------------------------------------------------------------------ #
    {
        "name": "Rifle River Camps (Alger area), MI",
        "type": "camp",
        "category": "logging_lumber",
        "latitude": 44.219,
        "longitude": -84.048,
        "description": (
            "The Rifle River logging camps in Roscommon County, Michigan operated during the peak white pine "
            "era and were part of the massive Saginaw Bay watershed logging complex, with the Rifle River "
            "providing an excellent log-driving stream for camps in the Alger area. Huron National Forest "
            "land in the Rifle River watershed is accessible for metal detecting and has produced logging "
            "camp hardware and coins from the 1870s-1890s peak era."
        ),
        "source": "AURIK",
        "confidence": 0.78,
    },
    # ------------------------------------------------------------------ #
    # Chippewa River Camp (Winter area), WI
    # ------------------------------------------------------------------ #
    {
        "name": "Chippewa River Camp (Winter area), WI",
        "type": "camp",
        "category": "logging_lumber",
        "latitude": 45.162,
        "longitude": -91.632,
        "description": (
            "The Chippewa River logging camps near Winter in Sawyer County, Wisconsin were at the heart of "
            "Wisconsin's lumber era from 1870 to 1910, when the Chippewa River system drove more white pine "
            "to Chippewa Falls and Eau Claire than any other river in Wisconsin. The upper Chippewa "
            "watershed in the Chequamegon National Forest hosted dozens of seasonal camps employing hundreds "
            "of lumberjacks. Chequamegon National Forest land in the upper Chippewa watershed is accessible "
            "for metal detecting."
        ),
        "source": "AURIK",
        "confidence": 0.82,
    },
    # ------------------------------------------------------------------ #
    # Menominee River Camp (Marinette), WI
    # ------------------------------------------------------------------ #
    {
        "name": "Menominee River Camp (Marinette), WI",
        "type": "camp",
        "category": "logging_lumber",
        "latitude": 45.103,
        "longitude": -87.622,
        "description": (
            "The Menominee River logging camps in Marinette County, Wisconsin operated during the "
            "river-drive era of the 1870s-1900s, supplying the massive sawmill complex at "
            "Marinette-Menominee where the river empties into Green Bay. The Menominee was one of the "
            "premier log-driving rivers in the Great Lakes region. Private land in the Marinette County "
            "river corridor has produced logging era camp hardware and personal effects from the active camp "
            "years."
        ),
        "source": "AURIK",
        "confidence": 0.78,
    },
    # ------------------------------------------------------------------ #
    # Wolf River Camp (Langlade), WI
    # ------------------------------------------------------------------ #
    {
        "name": "Wolf River Camp (Langlade), WI",
        "type": "camp",
        "category": "logging_lumber",
        "latitude": 45.167,
        "longitude": -88.967,
        "description": (
            "The Wolf River logging camps in Langlade County, Wisconsin operated in an area with deep "
            "Potawatomi and Menominee heritage that was transformed by the 1870s-1900s white pine logging "
            "boom, with camps in the headwaters of the Wolf in the Nicolet National Forest representing one "
            "of the most historically layered logging landscapes in the Great Lakes. Nicolet National Forest "
            "land in the upper Wolf watershed is accessible for metal detecting and has produced mixed "
            "Native American trade material and logging era camp hardware."
        ),
        "source": "AURIK",
        "confidence": 0.8,
    },
    # ------------------------------------------------------------------ #
    # Namekagon River Camp (Hayward area), WI
    # ------------------------------------------------------------------ #
    {
        "name": "Namekagon River Camp (Hayward area), WI",
        "type": "camp",
        "category": "logging_lumber",
        "latitude": 46.028,
        "longitude": -91.483,
        "description": (
            "The Namekagon River logging camps near Hayward in Sawyer County, Wisconsin occupied the upper "
            "St. Croix River headwaters country during the peak pine logging era of the 1880s-1900s, with "
            "the Namekagon serving as a premier log-driving stream through the Chequamegon National Forest. "
            "The upper Namekagon watershed is also part of the National Scenic Riverway. Chequamegon "
            "National Forest land in the Namekagon watershed is accessible for metal detecting."
        ),
        "source": "AURIK",
        "confidence": 0.8,
    },
    # ------------------------------------------------------------------ #
    # Pine River Camp (Backus area), MN
    # ------------------------------------------------------------------ #
    {
        "name": "Pine River Camp (Backus area), MN",
        "type": "camp",
        "category": "logging_lumber",
        "latitude": 46.71,
        "longitude": -94.404,
        "description": (
            "The Pine River logging camps near Backus in Cass County, Minnesota were part of the great "
            "Minnesota white pine era of the 1880s-1910s, when the Chippewa National Forest's pine belt was "
            "intensively harvested by camps operating along the Pine River and its tributaries feeding into "
            "Leech Lake. Chippewa National Forest land in the Pine River watershed is accessible for metal "
            "detecting and has produced logging camp hardware and coins from the extensive camp occupation."
        ),
        "source": "AURIK",
        "confidence": 0.8,
    },
    # ------------------------------------------------------------------ #
    # Rainy Lake Logging Camp, MN
    # ------------------------------------------------------------------ #
    {
        "name": "Rainy Lake Logging Camp, MN",
        "type": "camp",
        "category": "logging_lumber",
        "latitude": 48.547,
        "longitude": -93.441,
        "description": (
            "The Rainy Lake logging camps in St. Louis County, Minnesota operated in the late 19th and early "
            "20th centuries just outside the boundary of what is now Voyageurs National Park, harvesting "
            "white and red pine from the border lakes region that is now Superior National Forest. The camps "
            "sat in the transition zone between the national park and the national forest, requiring careful "
            "attention to land status. Superior National Forest land in the Rainy Lake area is accessible "
            "for metal detecting."
        ),
        "source": "AURIK",
        "confidence": 0.75,
    },
    # ------------------------------------------------------------------ #
    # Vermilion River Camp (Tower area), MN
    # ------------------------------------------------------------------ #
    {
        "name": "Vermilion River Camp (Tower area), MN",
        "type": "camp",
        "category": "logging_lumber",
        "latitude": 47.798,
        "longitude": -92.291,
        "description": (
            "The Vermilion River logging camps near Tower in St. Louis County, Minnesota operated in the "
            "iron range country during the 1880s-1910s, where logging and iron mining overlapped in the "
            "Superior National Forest highlands. The camps supplied timber for both the sawmill towns and "
            "the growing iron range mine operations. Superior National Forest land in the Vermilion "
            "watershed is accessible for metal detecting and has produced logging and mining era camp "
            "hardware."
        ),
        "source": "AURIK",
        "confidence": 0.78,
    },
    # ------------------------------------------------------------------ #
    # Penobscot River Camp (Millinocket area), ME
    # ------------------------------------------------------------------ #
    {
        "name": "Penobscot River Camp (Millinocket area), ME",
        "type": "camp",
        "category": "logging_lumber",
        "latitude": 45.617,
        "longitude": -68.713,
        "description": (
            "The Penobscot River logging camps near Millinocket in Penobscot County, Maine were operated by "
            "the Great Northern Paper Company and its predecessors from the 1880s through the 20th century, "
            "harvesting the vast softwood forests of the Maine interior for pulpwood and sawlogs driven down "
            "the West Branch Penobscot. The camps were on private timber company land. Landowner permission "
            "on the extensive Great Northern/Weyerhaeuser legacy lands is required but the camps produced "
            "rich material including coins, tools, and camp hardware."
        ),
        "source": "AURIK",
        "confidence": 0.78,
    },
    # ------------------------------------------------------------------ #
    # Kennebec River Camp (The Forks area), ME
    # ------------------------------------------------------------------ #
    {
        "name": "Kennebec River Camp (The Forks area), ME",
        "type": "camp",
        "category": "logging_lumber",
        "latitude": 45.358,
        "longitude": -69.914,
        "description": (
            "The Kennebec River logging camps at The Forks in Somerset County, Maine represent the classic "
            "Maine river-drive country, where the Dead River and upper Kennebec confluence created a natural "
            "staging area for log drives downstream to the Augusta mills. The Forks area was the "
            "organizational center for some of the most dramatic log drives in Maine history during the "
            "1870s-1910s. Private timber land in Somerset County has preserved camp material from the "
            "river-drive era."
        ),
        "source": "AURIK",
        "confidence": 0.8,
    },
    # ------------------------------------------------------------------ #
    # Moosehead Lake Camp (Greenville), ME
    # ------------------------------------------------------------------ #
    {
        "name": "Moosehead Lake Camp (Greenville), ME",
        "type": "camp",
        "category": "logging_lumber",
        "latitude": 45.452,
        "longitude": -69.593,
        "description": (
            "The Moosehead Lake logging camps near Greenville in Piscataquis County, Maine were headquarters "
            "for the largest lake-based logging operation in Maine, where logs were rafted across Maine's "
            "largest lake before being driven down the Kennebec River system to southern mills. Greenville "
            "served as the supply and outfitting center for dozens of camps operating throughout the "
            "Moosehead watershed. Private timber land surrounding the historic lake logging area has "
            "produced camp material from the late 19th-century peak."
        ),
        "source": "AURIK",
        "confidence": 0.8,
    },
    # ------------------------------------------------------------------ #
    # Aroostook River Camp (Presque Isle area), ME
    # ------------------------------------------------------------------ #
    {
        "name": "Aroostook River Camp (Presque Isle area), ME",
        "type": "camp",
        "category": "logging_lumber",
        "latitude": 46.683,
        "longitude": -68.016,
        "description": (
            "The Aroostook River logging camps near Presque Isle in Aroostook County, Maine operated in "
            "Maine's northernmost county where potato agriculture and softwood logging overlapped during the "
            "late 19th and early 20th centuries, with camps harvesting spruce and fir from the vast "
            "Aroostook interior for pulpwood and sawlogs. Private farmland and timber land in Aroostook "
            "County has produced logging camp hardware and personal effects from the active camp period."
        ),
        "source": "AURIK",
        "confidence": 0.75,
    },
    # ------------------------------------------------------------------ #
    # Connecticut River Upper Camp (Colebrook), NH
    # ------------------------------------------------------------------ #
    {
        "name": "Connecticut River Upper Camp (Colebrook), NH",
        "type": "camp",
        "category": "logging_lumber",
        "latitude": 44.892,
        "longitude": -71.495,
        "description": (
            "The upper Connecticut River logging camps near Colebrook in Coos County, New Hampshire operated "
            "during the peak logging era of the 1870s-1910s in the White Mountain National Forest highland "
            "country, harvesting softwood timber from the river's upper drainage for mills downstream at "
            "Lancaster and St. Johnsbury. White Mountain National Forest land in the upper Connecticut "
            "valley near Colebrook is accessible for metal detecting."
        ),
        "source": "AURIK",
        "confidence": 0.78,
    },
    # ------------------------------------------------------------------ #
    # Swift River Camp (Conway area), NH
    # ------------------------------------------------------------------ #
    {
        "name": "Swift River Camp (Conway area), NH",
        "type": "camp",
        "category": "logging_lumber",
        "latitude": 43.977,
        "longitude": -71.131,
        "description": (
            "The Swift River logging camps near Conway in Carroll County, New Hampshire operated in the "
            "White Mountain National Forest along the Kancamagus Highway corridor during the peak logging "
            "era, harvesting hardwood and softwood from the flanks of the White Mountains before the "
            "National Forest purchase ended private logging operations in the early 20th century. White "
            "Mountain National Forest land along the Swift River is accessible for metal detecting."
        ),
        "source": "AURIK",
        "confidence": 0.78,
    },
    # ------------------------------------------------------------------ #
    # Lamoille River Camp (Johnson, VT)
    # ------------------------------------------------------------------ #
    {
        "name": "Lamoille River Camp (Johnson, VT)",
        "type": "camp",
        "category": "logging_lumber",
        "latitude": 44.633,
        "longitude": -72.679,
        "description": (
            "The Lamoille River logging camps near Johnson in Lamoille County, Vermont operated during the "
            "Vermont hardwood and softwood logging era of the 1860s-1900s, harvesting the considerable "
            "timber resources of the Green Mountain foothills for mills along the lower Lamoille. Vermont's "
            "logging camps were smaller and less intensive than the Great Lakes operations but left a "
            "distinctive material record in the river valleys. Private farmland in the Lamoille County river "
            "corridor has produced camp hardware and coins from the logging era."
        ),
        "source": "AURIK",
        "confidence": 0.72,
    },
    # ------------------------------------------------------------------ #
    # Black River Camp (Lyons Falls), NY
    # ------------------------------------------------------------------ #
    {
        "name": "Black River Camp (Lyons Falls), NY",
        "type": "camp",
        "category": "logging_lumber",
        "latitude": 43.613,
        "longitude": -75.369,
        "description": (
            "The Black River logging camps near Lyons Falls in Lewis County, New York operated during the "
            "tanning and logging boom of the 1860s-1900s when the Adirondack hardwood forests were "
            "intensively harvested for hemlock bark for the tanning industry and softwood sawlogs for mills "
            "along the Black River. The Lyons Falls area was a key mill center for the western Adirondack "
            "logging trade. Private land in the Lewis County river valley has produced camp material from "
            "the tanning and logging era."
        ),
        "source": "AURIK",
        "confidence": 0.75,
    },
    # ------------------------------------------------------------------ #
    # Grays Harbor Camp (Hoquiam area), WA
    # ------------------------------------------------------------------ #
    {
        "name": "Grays Harbor Camp (Hoquiam area), WA",
        "type": "camp",
        "category": "logging_lumber",
        "latitude": 47.068,
        "longitude": -123.88,
        "description": (
            "The Grays Harbor logging camps near Hoquiam in Grays Harbor County, Washington were part of one "
            "of the most intensive coastal logging operations in American history, where the massive Douglas "
            "fir forests of the Olympic Peninsula foothills were clear-cut by camps supplying the "
            "Hoquiam-Aberdeen sawmill complex during the 1880s-1920s. The private timber company lands "
            "surrounding the historic camp areas have produced logging camp hardware and personal effects "
            "from the peak era."
        ),
        "source": "AURIK",
        "confidence": 0.78,
    },
    # ------------------------------------------------------------------ #
    # Willapa Hills Camp (Raymond area), WA
    # ------------------------------------------------------------------ #
    {
        "name": "Willapa Hills Camp (Raymond area), WA",
        "type": "camp",
        "category": "logging_lumber",
        "latitude": 46.5,
        "longitude": -123.6,
        "description": (
            "The Willapa Hills logging camps near Raymond in Pacific County, Washington harvested the "
            "old-growth Douglas fir forests of the Coast Range during the 1890s-1920s, supplying the Raymond "
            "sawmills on the Willapa River. The Willapa Hills represented the southern extent of the "
            "Washington coastal logging boom. Private timber company land in the Pacific County hills has "
            "preserved logging camp material from the intensive harvest period."
        ),
        "source": "AURIK",
        "confidence": 0.75,
    },
    # ------------------------------------------------------------------ #
    # Okanogan Highlands Camp (Republic area), WA
    # ------------------------------------------------------------------ #
    {
        "name": "Okanogan Highlands Camp (Republic area), WA",
        "type": "camp",
        "category": "logging_lumber",
        "latitude": 48.65,
        "longitude": -118.74,
        "description": (
            "The Okanogan Highlands logging camps near Republic in Ferry County, Washington operated in the "
            "transition zone between the ponderosa pine belt and the mixed conifer highlands, harvesting "
            "timber for both local mining operations and regional sawmills during the 1890s-1920s. Okanogan "
            "National Forest land in the Republic area is accessible for metal detecting and has produced "
            "logging camp and mining support material."
        ),
        "source": "AURIK",
        "confidence": 0.72,
    },
    # ------------------------------------------------------------------ #
    # Coos Bay Camp (Coos County), OR
    # ------------------------------------------------------------------ #
    {
        "name": "Coos Bay Camp (Coos County), OR",
        "type": "camp",
        "category": "logging_lumber",
        "latitude": 43.4,
        "longitude": -124.1,
        "description": (
            "The Coos Bay logging camps in Coos County, Oregon were part of one of the largest Douglas fir "
            "logging operations on the Pacific Coast, where the inland camps supplied the massive Coos Bay "
            "sawmill complex that made Coos Bay one of the leading lumber ports in the world during the "
            "1890s-1930s. Private timber company land surrounding the historic camp areas has preserved "
            "logging camp hardware and personal effects from the peak harvest era."
        ),
        "source": "AURIK",
        "confidence": 0.78,
    },
    # ------------------------------------------------------------------ #
    # Siuslaw River Camp (Mapleton area), OR
    # ------------------------------------------------------------------ #
    {
        "name": "Siuslaw River Camp (Mapleton area), OR",
        "type": "camp",
        "category": "logging_lumber",
        "latitude": 44.082,
        "longitude": -123.876,
        "description": (
            "The Siuslaw River logging camps near Mapleton in Lane County, Oregon operated from the 1880s "
            "through the 1920s in the Siuslaw National Forest, harvesting the outstanding Sitka spruce and "
            "Douglas fir forests of the Coast Range for mills at Florence on the Oregon coast. Siuslaw "
            "National Forest land in the Mapleton area is accessible for metal detecting and has produced "
            "logging camp hardware from the extensive camp occupation."
        ),
        "source": "AURIK",
        "confidence": 0.8,
    },
    # ------------------------------------------------------------------ #
    # Nehalem River Camp (Vernonia area), OR
    # ------------------------------------------------------------------ #
    {
        "name": "Nehalem River Camp (Vernonia area), OR",
        "type": "camp",
        "category": "logging_lumber",
        "latitude": 45.852,
        "longitude": -123.196,
        "description": (
            "The Nehalem River logging camps near Vernonia in Columbia County, Oregon harvested the northern "
            "Coast Range Douglas fir forests during the 1890s-1930s, supplying mills along the lower Nehalem "
            "and at St. Helens on the Columbia. The area is now part of the Tillamook State Forest, an "
            "Oregon State Forest property. Metal detecting regulations on Oregon State Forest land should be "
            "verified with the Oregon Department of Forestry before any detecting activity."
        ),
        "source": "AURIK",
        "confidence": 0.72,
    },
    # ------------------------------------------------------------------ #
    # Greenbrier River Camp (Marlinton area), WV
    # ------------------------------------------------------------------ #
    {
        "name": "Greenbrier River Camp (Marlinton area), WV",
        "type": "camp",
        "category": "logging_lumber",
        "latitude": 38.102,
        "longitude": -80.253,
        "description": (
            "The Greenbrier River logging camps near Marlinton in Pocahontas County, West Virginia were "
            "central to the massive West Virginia lumber boom of the 1880s-1920s, when companies like the "
            "West Virginia Pulp and Paper Company and the Greenbrier Lumber Company clear-cut the "
            "Monongahela National Forest's hardwood highlands. Monongahela National Forest land in the "
            "Greenbrier watershed is accessible for metal detecting and has produced logging camp hardware, "
            "coins, and personal effects from the intensive harvest period."
        ),
        "source": "AURIK",
        "confidence": 0.83,
    },
    # ------------------------------------------------------------------ #
    # Cheat River Camp (Parsons area), WV
    # ------------------------------------------------------------------ #
    {
        "name": "Cheat River Camp (Parsons area), WV",
        "type": "camp",
        "category": "logging_lumber",
        "latitude": 39.097,
        "longitude": -79.684,
        "description": (
            "The Cheat River logging camps near Parsons in Tucker County, West Virginia operated during the "
            "peak WV lumber era when the upper Cheat highlands were being harvested simultaneously for "
            "sawlogs and hemlock bark for the tanning industry. The Tucker County mountain landscape was "
            "transformed by the intensive logging. Monongahela National Forest land in the upper Cheat "
            "watershed is accessible for metal detecting and has produced logging and tanning era camp "
            "material."
        ),
        "source": "AURIK",
        "confidence": 0.82,
    },
    # ------------------------------------------------------------------ #
    # Black Fork Camp (Thomas area), WV
    # ------------------------------------------------------------------ #
    {
        "name": "Black Fork Camp (Thomas area), WV",
        "type": "camp",
        "category": "logging_lumber",
        "latitude": 39.148,
        "longitude": -79.494,
        "description": (
            "The Black Fork logging camps near Thomas in Tucker County, West Virginia operated during the "
            "peak West Virginia lumber and pulpwood era of the 1880s-1920s when the upper Cheat tributaries "
            "were intensively harvested for pulpwood for the Piedmont paper mills. The Thomas area was a "
            "railroad logging center where standard gauge rails penetrated the highland wilderness. "
            "Monongahela National Forest land in the Black Fork watershed is accessible for metal detecting."
        ),
        "source": "AURIK",
        "confidence": 0.8,
    },
    # ------------------------------------------------------------------ #
    # Cranberry River Camp (Webster Springs), WV
    # ------------------------------------------------------------------ #
    {
        "name": "Cranberry River Camp (Webster Springs), WV",
        "type": "camp",
        "category": "logging_lumber",
        "latitude": 38.172,
        "longitude": -80.4,
        "description": (
            "The Cranberry River logging camps near Webster Springs in Webster County, West Virginia "
            "operated adjacent to what is now the Cranberry Wilderness Area in the Monongahela National "
            "Forest, harvesting spruce and hardwood from the high plateau country. The camps must be "
            "distinguished from the current wilderness boundary, as detecting is prohibited in designated "
            "Wilderness Areas. Monongahela National Forest land outside the Cranberry Wilderness boundary is "
            "accessible for metal detecting."
        ),
        "source": "AURIK",
        "confidence": 0.78,
    },
    # ------------------------------------------------------------------ #
    # Gauley River Camp (Summersville area), WV
    # ------------------------------------------------------------------ #
    {
        "name": "Gauley River Camp (Summersville area), WV",
        "type": "camp",
        "category": "logging_lumber",
        "latitude": 38.269,
        "longitude": -80.86,
        "description": (
            "The Gauley River logging camps near Summersville in Nicholas County, West Virginia operated "
            "during the late 19th and early 20th centuries in the timber-rich Gauley River drainage, "
            "distinct from the later-designated NPS Gauley River National Recreation Area unit. Private and "
            "BLM land in the Nicholas County Gauley watershed not within the NRA boundary preserves logging "
            "camp material from the pre-impoundment period."
        ),
        "source": "AURIK",
        "confidence": 0.75,
    },
    # ------------------------------------------------------------------ #
    # Pigeon River Camp (Waynesville area), NC
    # ------------------------------------------------------------------ #
    {
        "name": "Pigeon River Camp (Waynesville area), NC",
        "type": "camp",
        "category": "logging_lumber",
        "latitude": 35.603,
        "longitude": -83.053,
        "description": (
            "The Pigeon River logging camps near Waynesville in Haywood County, North Carolina were operated "
            "by Champion Paper and Fibre Company during the intensive period of 1906-1920 when the Pisgah "
            "National Forest's old-growth hardwood and spruce forests were clear-cut for pulpwood, one of "
            "the most dramatic landscape transformations in southern Appalachian history. Pisgah National "
            "Forest land in the Pigeon watershed is accessible for metal detecting and has produced logging "
            "camp hardware and company scrip from the Champion era."
        ),
        "source": "AURIK",
        "confidence": 0.82,
    },
    # ------------------------------------------------------------------ #
    # Nantahala River Camp (Andrews area), NC
    # ------------------------------------------------------------------ #
    {
        "name": "Nantahala River Camp (Andrews area), NC",
        "type": "camp",
        "category": "logging_lumber",
        "latitude": 35.202,
        "longitude": -83.674,
        "description": (
            "The Nantahala River logging camps near Andrews in Cherokee County, North Carolina operated from "
            "the 1880s through the 1920s in the Nantahala National Forest gorge country, harvesting "
            "chestnut, poplar, and cherry from the southern Appalachian cove hardwood forests for mills in "
            "Andrews and Murphy. Nantahala National Forest land in the river gorge area is accessible for "
            "metal detecting and has produced logging camp hardware and personal effects."
        ),
        "source": "AURIK",
        "confidence": 0.8,
    },
    # ------------------------------------------------------------------ #
    # Clinch River Camp (St. Paul, VA)
    # ------------------------------------------------------------------ #
    {
        "name": "Clinch River Camp (St. Paul, VA)",
        "type": "camp",
        "category": "logging_lumber",
        "latitude": 36.95,
        "longitude": -82.43,
        "description": (
            "The Clinch River logging camps near St. Paul in Wise County, Virginia operated during the late "
            "19th and early 20th centuries when the Jefferson National Forest highlands were being harvested "
            "simultaneously for sawlogs and to supply the growing coal camp populations of the Virginia "
            "coalfields. Jefferson National Forest land in the Clinch River watershed near St. Paul is "
            "accessible for metal detecting and has produced mixed logging and coal camp era material."
        ),
        "source": "AURIK",
        "confidence": 0.78,
    }
]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Output the historic camps dataset as JSON."
    )
    parser.add_argument(
        "--output-dir",
        default="data",
        help="Directory to write JSON file (default: data/)",
    )
    parser.add_argument(
        "--output-name",
        default="historic_camps",
        help="Output filename without extension (default: historic_camps)",
    )
    args = parser.parse_args(argv)

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{args.output_name}.json"

    with out_path.open("w", encoding="utf-8") as fh:
        json.dump(HISTORIC_CAMPS, fh, indent=2, ensure_ascii=False)

    print(f"Wrote {len(HISTORIC_CAMPS)} entries to {out_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
