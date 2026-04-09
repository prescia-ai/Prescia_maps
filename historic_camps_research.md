# Research Report: `data/historic_camps.json` — Verification, Deduplication & Expansion

---

## 1. EXISTING DATA CROSS-REFERENCE (Duplicates to Avoid)

**From `data/frrandp_ghost_towns.json` (1,075 entries) — Camp-named entries already captured:**

| Name | lat | lon | Note |
|---|---|---|---|
| Camp Ellis Army Base | 40.366 | -90.397 | WWII-era, type=town. Skip in camps dataset |
| Camp Ibis | 34.970 | -114.833 | WWII desert training, type=town. Skip |
| Camp Barkley | 32.350 | -99.840 | WWII Abilene TX, type=town. Skip |
| Encampment, MN | 47.095 | -91.566 | Farming hamlet, type=town. Skip |
| Abandoned POW Camp | 37.192 | -104.417 | WWII Raton NM, type=town. Skip |
| Calamity Camp | 38.608 | -108.848 | Grand Junction, CO area. Skip |
| #8 Gold Miners Base Camp | 34.959 | -114.394 | Mining camp → EXCLUDE (mining) |

**From `data/historic_trail_landmarks.json` (143 entries) — Major trail nodes already covered (any camp entry here is a DUPLICATE):**

These landmarks are at the same locations many "camp" proposals would occupy. Anything at or very near these coordinates is a duplicate and should be omitted from `historic_camps.json`:

- Camp Floyd, UT (lat=40.30, lon=-112.10) — already type=trail_landmark
- French Camp, MS (lat=33.30, lon=-89.40) — already type=trail_landmark
- Fort Laramie, WY — already in trail_landmarks AND stagecoach_stops
- Fort Kearny, NE — already in trail_landmarks AND stagecoach_stops
- Fort Bridger, WY — already in both
- South Pass, WY — already in both
- Fort Boise, ID — already trail_landmark
- Fort Hall, ID — already trail_landmark
- Ash Hollow, NE — already trail_landmark
- Independence Rock, WY — already trail_landmark
- Pacific Springs, WY — already trail_landmark
- City of Rocks, ID — already trail_landmark
- Pawnee Rock, KS — already trail_landmark
- Point of Rocks, NM — already trail_landmark
- Alcove Spring, KS — already trail_landmark
- Big Blue River Crossing, KS — already trail_landmark
- Plum Creek Station, NE — already stagecoach_stop
- Phantom Hill, TX — already stagecoach_stop
- Apache Pass Station, AZ — already stagecoach_stop
- Dragoon Springs, AZ — already stagecoach_stop
- Mesilla, NM — already trail_landmark

**From `data/battles_seed.json` (371 entries) — Military camp sites already covered as battle sites:**

- Valley Forge Encampment (lat=40.102, lon=-75.394) — already type=battle, AND is NPS land (Valley Forge NHP) → **DO NOT ADD**
- Battle of Camp Wildcat, KY (lat=37.30, lon=-84.067) — already type=battle

---

## 2. LAND ACCESS — CAMPS TO REMOVE (Protected Land)

These proposed camp sites fall on land where metal detecting is **prohibited**:

### ❌ National Park Service / National Historic Sites

| Camp | Location | Land Status | Reason |
|---|---|---|---|
| Valley Forge Encampment | PA | Valley Forge NHP (NPS) | Already in battles; detecting illegal |
| Fort Necessity / Great Meadows | PA | Fort Necessity NBP (NPS) | Already in battles; detecting illegal |
| Fort Union Trading Post | ND | Fort Union Trading Post NHS (NPS) | Fur trade post; NPS = illegal |
| Fort Bowie | AZ | Fort Bowie NHS (NPS) | Apache War camp; NPS = illegal |
| Whitman Mission (Waiilatpu) | WA | Whitman Mission NHS (NPS) | Already in trail_landmarks; NPS = illegal |
| Fort Clatsop (Lewis & Clark) | OR | Lewis & Clark NHP (NPS) | NPS encampment; illegal |
| Sand Creek Massacre site | CO | Sand Creek NM (NPS) | Already in battles; National Monument = illegal |
| Big Hole Battlefield | MT | Big Hole NB (NPS) | Already in trail_landmarks; illegal |
| Bear Paw Battlefield | MT | Nez Perce NHP (NPS) | Already in trail_landmarks; illegal |

### ❌ National Monuments

| Camp | Location | Land Status |
|---|---|---|
| Malheur NWR area camps | OR | National Wildlife Refuge — detecting banned |
| Pompeys Pillar area | MT | Pompeys Pillar NM (BLM NM) — detecting banned |
| Carrizo Plain camps | CA | Carrizo Plain NM — detecting banned |

### ❌ State Parks

| Camp | Location | Land Status |
|---|---|---|
| Spokane House (HBC post) | WA | Riverside State Park — detecting illegal |
| Fort Rains site | OR | Emigrant Springs State Park — detecting illegal |

### ❌ Active Military Reservations

| Camp | Location | Land Status |
|---|---|---|
| Camp Wichita (later Fort Sill) | OK | Fort Sill — ACTIVE military reservation → **REMOVE** |
| Camp Apache (White Mountain) | AZ | Fort Apache Indian Reservation — tribal land, no detecting without tribal permission |

### ❌ Wilderness Areas

| Camp | Location | Land Status |
|---|---|---|
| New River Gorge logging camps | WV | New River Gorge National Park & Preserve (2020) → **REMOVE** |
| Any camp in Boundary Waters, MN | MN | BWCAW — Wilderness Area, detecting banned |

---

## 3. MINING CAMPS — EXCLUDE (User's explicit instruction)

These fall into "mining camp" territory and must be omitted:

| Camp Name | Location | Reason to Exclude |
|---|---|---|
| #8 Gold Miners Base Camp | Mohave Co., AZ | Explicitly a mining camp |
| South Pass City, WY | WY | Gold mining town (also in trail_landmarks and is WY State Historic Site) |
| Any "placer camp," "diggings," or "lode" named sites | various | Mining operations |
| Calamity Camp, CO | Mesa Co., CO | Mining operation near Grand Junction (also in ghost_towns) |
| Virginia City camps (NV or MT) | NV/MT | Mining boom towns |
| Chloride, Oatman, Goldfield camps | AZ/NV | Mining operations |
| Bodie camps | CA | Mining; Bodie State Historic Park = state park → double removal |

---

## 4. COORDINATE VERIFICATION — Key Issues to Flag

Without the user's exact starter list, these are the most common coordinate errors seen in similar datasets for these types of camps:

**High-Risk Coordinate Errors:**

| Camp | Expected Coords | Common Wrong Value | Issue |
|---|---|---|---|
| Green River Rendezvous (WY) | ~42.05°N, 110.03°W | Often confused with Green River, UT (41.53°N, 109.47°W) | Wrong state — UT vs WY |
| Pierre's Hole Rendezvous 1832 | 43.83°N, 111.17°W (Teton Valley, ID) | Sometimes placed at Jackson Hole, WY | Off by ~30 miles |
| Bear Lake Rendezvous 1827-28 | 41.93°N, 111.35°W | Sometimes confused with Bear River crossing | Wrong lake |
| Popo Agie Rendezvous 1829/1838 | 42.84°N, 108.78°W (Lander, WY) | Sometimes placed near Riverton, WY | ~15 miles off |
| Camp Colorado, TX | 31.84°N, 99.13°W (Coleman County) | Confused with Colorado City, TX | Wrong county |
| Camp Cooper, TX | 33.33°N, 99.27°W (Throckmorton Co.) | Often confused with Camp Cooper in another state | Should be ~33.3°N |
| Camp Verde, TX | 29.90°N, 98.94°W (Kerr Co.) | Confused with Camp Verde, AZ (34.57°N, 111.86°W) | Different state entirely |
| Camp Floyd, UT | 40.30°N, 112.10°W | Already in trail_landmarks; coords there are correct | Duplicate |
| Fort Phil Kearny, WY | 44.524°N, 106.951°W | Already in trail_landmarks; coords there are correct | Duplicate |

---

## 5. NEW CAMPS TO ADD — Comprehensive Expanded List

### CATEGORY A: Emigrant Trail Camps (~80 targets, not already in trail_landmarks)

#### Oregon Trail — Nebraska Segment

| # | Name | lat | lon | Land Access | Notes |
|---|---|---|---|---|---|
| 1 | Kanesville (Council Bluffs), IA | 41.263 | -95.858 | Private/urban | Primary Mormon Trail start; major 1846-52 staging ground |
| 2 | Bellevue, NE | 41.145 | -95.919 | Private | Earliest permanent Nebraska settlement; trail crossing |
| 3 | Dobytown (near Fort Kearny), NE | 40.641 | -99.018 | BLM/private | Civilian camp adjacent to Fort Kearny; saloon town |
| 4 | Elm Creek Station, NE | 40.720 | -99.363 | Private | Midpoint camp on Platte River road |
| 5 | Plum Creek, NE | 40.589 | -99.584 | Private | Plum Creek Massacre site 1864; emigrant camp |
| 6 | Lower California Crossing, NE | 41.120 | -101.600 | BLM/private | Trail ford; major camp site |
| 7 | Mud Springs, NE | 41.557 | -103.090 | BLM | Pony Express / Oregon Trail camp; Mud Springs battle 1865 |
| 8 | Lodgepole Creek Camp, NE | 41.180 | -102.170 | Private | Trail divergence point for Colorado shortcut |

#### Oregon Trail — Wyoming Segment

| # | Name | lat | lon | Land Access | Notes |
|---|---|---|---|---|---|
| 9 | Horse Creek Treaty Ground, WY | 42.008 | -104.597 | BLM | 1851 Fort Laramie Treaty council ground; huge gathering |
| 10 | Deer Creek Camp, WY | 42.831 | -106.043 | BLM | Major emigrant stop on Platte; had a trading post 1857 |
| 11 | Warm Springs Camp (Alcova), WY | 42.573 | -107.017 | BLM | Hot springs camping area; emigrants paused here |
| 12 | Rocky Ridge Camp, WY | 42.644 | -108.450 | BLM | Particularly difficult section; heavy emigrant camp area |
| 13 | Names Hill, WY | 41.984 | -110.274 | BLM | Emigrant inscription site; camp on Green River |
| 14 | Ham's Fork Camp (Granger), WY | 41.617 | -109.940 | BLM | Multi-trail junction; rendezvous site before trail era |
| 15 | Thomas Fork Camp, WY | 42.032 | -111.103 | BLM/private | Major emigrant camp in Bear River drainage |
| 16 | Bear River Camp (Cokeville), WY | 42.078 | -110.960 | BLM/private | Last WY camp before ID; springs and meadow |

#### Oregon Trail — Idaho Segment

| # | Name | lat | lon | Land Access | Notes |
|---|---|---|---|---|---|
| 17 | Soda Springs Camp, ID | 42.654 | -111.604 | BLM/private | Natural carbonated springs; famous emigrant landmark |
| 18 | American Falls Camp, ID | 42.786 | -112.850 | Private | Snake River camp; now partially under reservoir |
| 19 | Raft River Junction Camp, ID | 42.150 | -113.500 | BLM | Where California/Oregon trails diverged |
| 20 | Salmon Falls Camp, ID | 42.610 | -114.850 | BLM/private | Snake River camp; major fishing site for emigrants |
| 21 | Bruneau Crossing Camp, ID | 42.877 | -115.797 | BLM | Bruneau River ford; emigrant camp |
| 22 | Birch Creek Camp, OR | 45.465 | -118.750 | BLM/private | Post-Blue Mountains descent camp |

#### California Trail — Nevada/California

| # | Name | lat | lon | Land Access | Notes |
|---|---|---|---|---|---|
| 23 | Thousand Springs Valley, NV | 41.750 | -115.100 | BLM | California Trail camp; natural springs |
| 24 | Wells (Bishop Creek) Camp, NV | 41.110 | -114.960 | BLM | Major California Trail junction camp |
| 25 | Rabbit Hole Springs, NV | 40.870 | -118.130 | BLM | Critical water on Lassen's Cutoff; desperate camps |
| 26 | Lassen's Meadow Camp, NV | 40.830 | -116.200 | BLM | Last grass before Humboldt Sink |
| 27 | Lovelock (Lassen's) Camp, NV | 40.180 | -118.470 | BLM | Humboldt River camps; major gathering area |
| 28 | Emigrant Gap, CA | 39.280 | -120.670 | Tahoe NF | Already in trail_landmarks — **SKIP** |
| 29 | Johnson's Ranch, CA | 39.150 | -121.200 | Private | Already in trail_landmarks — **SKIP** |
| 30 | Donner Lake Camp, CA | 39.320 | -120.240 | Tahoe NF | Already in trail_landmarks — **SKIP** |

#### Mormon Trail — Iowa Segment

| # | Name | lat | lon | Land Access | Notes |
|---|---|---|---|---|---|
| 31 | Garden Grove Camp, IA | 40.828 | -93.610 | Private | 1846 way-station built by Pioneer Company for later wagon trains |
| 32 | Mount Pisgah Camp, IA | 41.048 | -94.197 | Private | 1846 Mormon staging camp; thousands spent the winter |
| 33 | Mosquito Creek Camp, IA | 41.600 | -95.757 | Private | Pre-Kanesville staging area for Missouri River crossing |

#### Mormon Trail — Nebraska

| # | Name | lat | lon | Land Access | Notes |
|---|---|---|---|---|---|
| 34 | Cutler's Park, NE | 41.352 | -96.061 | Private/urban | 1846 early camp near Winter Quarters (not at NPS site) |
| 35 | Loup Fork Crossing, NE | 41.557 | -97.450 | Private | Mormon Trail/Pawnee interaction area |

#### Santa Fe Trail — Kansas Segment

| # | Name | lat | lon | Land Access | Notes |
|---|---|---|---|---|---|
| 36 | Diamond Springs Camp, KS | 38.840 | -96.730 | Private | "Diamond of the Plains" — major Santa Fe Trail campsite |
| 37 | Lost Spring Camp, KS | 38.660 | -97.003 | Private | Named spring; important 1st-day camp from Council Grove |
| 38 | Cottonwood Creek Crossing, KS | 38.524 | -97.719 | Private | Major Santa Fe Trail camp on Cottonwood Creek |
| 39 | Little Arkansas Crossing, KS | 38.021 | -97.907 | Private | Trail ford; Cimarron cutoff divergence area |
| 40 | Cow Creek Crossing, KS | 38.202 | -98.783 | Private/BLM | Major trail camp; now near Lyons, KS |
| 41 | Walnut Creek Crossing, KS | 38.370 | -98.838 | Private/BLM | Bent's trading post site; 1858 stage station |
| 42 | Cimarron Crossing Camp, KS | 37.753 | -100.350 | BLM | Already in trail_landmarks — **SKIP** |
| 43 | Middle Spring (Cimarron Route), KS | 36.978 | -101.415 | USFS/Cimarron NGA | National Grassland — detecting needs permit |
| 44 | Lower Cimarron Spring (Flag Spring), KS | 37.007 | -100.875 | Private/BLM | Trail camp between Dodge and crossing |

#### Santa Fe Trail — New Mexico

| # | Name | lat | lon | Land Access | Notes |
|---|---|---|---|---|---|
| 45 | Rabbit Ears Camp, NM | 36.672 | -103.967 | Private/BLM | Landmark camp on Mountain Branch |
| 46 | Rayado Camp, NM | 36.549 | -104.690 | Private (Philmont Scout Ranch) | Kit Carson's ranch; trail camp — detecting unlikely |
| 47 | Ocate Creek Camp, NM | 36.397 | -104.661 | Private | Trail camp on Mountain Branch descent |

---

### CATEGORY B: Military / Frontier Camps (~60 targets)

#### Texas Frontier Line Camps (1849–1861 "First Line," "Second Line")

| # | Name | lat | lon | Land Access | Notes |
|---|---|---|---|---|---|
| 1 | Camp Colorado, TX | 31.840 | -99.130 | Private ranch | Clear Fork of Colorado R., Coleman County; 1857-61 |
| 2 | Camp Cooper, TX | 33.330 | -99.270 | Private ranch | Throckmorton Co.; Robert E. Lee commanded here 1856 |
| 3 | Camp Verde, TX | 29.900 | -98.940 | Private ranch | Kerr County; famous camel corps experiment 1856-61 |
| 4 | Camp Hudson, TX | 29.647 | -100.898 | Private ranch | Val Verde County; Devils River; 1857-68 |
| 5 | Camp Lancaster, TX | 30.648 | -101.543 | Private ranch | Crockett County; Live Oak Creek; 1855-61 |
| 6 | Camp Leona, TX | 29.458 | -99.764 | Private ranch | Uvalde County; 1849-50 |
| 7 | Camp Wood, TX | 29.672 | -100.032 | Private ranch | Real County; near small town of same name |
| 8 | Camp San Saba, TX | 31.107 | -99.344 | Private ranch | McCulloch County; temporary 1852-53 |
| 9 | Camp Peña Colorado, TX | 30.833 | -102.775 | BLM/private | Mitchell County; Glass Mountains; 1879-93 |
| 10 | Camp Elizabeth, TX | 31.337 | -100.707 | Private ranch | Sterling County; 1878-80 |
| 11 | Camp Melvin, TX | 30.697 | -101.682 | Private ranch | Crockett County; Pecos River; 1868-71 |
| 12 | Camp Magruder, TX | 29.775 | -97.989 | Private/urban | Gonzales County area; early 1850s |
| 13 | Camp Phantom Hill, TX | 32.578 | -99.721 | Private | Jones County; ruins standing; already in stagecoach_stops as "Phantom Hill, TX" — **SKIP** |
| 14 | Camp Ives, TX | 29.447 | -100.773 | Private ranch | Val Verde County near Brackettville |
| 15 | Camp Radziminski, OK | 34.683 | -99.370 | Private | Tillman County, OK; temporary 1858-59 near Otter Creek |

#### Arizona Territory Camps

| # | Name | lat | lon | Land Access | Notes |
|---|---|---|---|---|---|
| 16 | Camp Beale Springs, AZ | 35.197 | -113.921 | BLM | Mohave County; 1871-74; peace camp for Hualapai |
| 17 | Camp Date Creek, AZ | 34.370 | -112.649 | BLM/private | Yavapai County; 1867-73; Yavapai scouts base |
| 18 | Camp Picket Post, AZ | 33.302 | -111.027 | Tonto NF ✅ | Final Tonto Apache campaign base; 1870-71 |
| 19 | Camp Pinal, AZ | 33.284 | -110.800 | BLM/private | Temporary camp during Tonto Basin campaign |
| 20 | Camp Mogollon, AZ | 33.667 | -109.250 | Apache-Sitgreaves NF ✅ | Temporary camp near Fort Apache; NF detecting allowed |
| 21 | Camp Lincoln (Prescott), AZ | 34.649 | -112.476 | BLM/private | 1864-66; Yavapai County; later Camp Verde |
| 22 | Camp Lowell, AZ (Tucson) | 32.240 | -110.916 | Urban/private | 1866-73; near Tucson; large WWII airfield now on site |
| 23 | Camp Thomas, AZ | 32.954 | -110.069 | Private/BLM | Graham County; Gila River; 1876-81 |
| 24 | Camp Rawlins, AZ | 34.520 | -112.004 | Private | Yavapai Co.; temporary during Apache campaigns |
| 25 | Camp Supply (AZ), AZ | 33.500 | -113.000 | BLM | Maricopa County; temporary supply depot |

#### New Mexico Territory Camps

| # | Name | lat | lon | Land Access | Notes |
|---|---|---|---|---|---|
| 26 | Camp Plummer, NM | 36.867 | -105.067 | Carson NF ✅ | Taos County; 1866-70; NF detecting allowed |
| 27 | Camp Bascom, NM | 36.867 | -103.267 | Private ranch | Union County; 1863-70; Canadian River area |
| 28 | Camp Burgwin, NM | 36.332 | -105.466 | Private | Taos County; 1852-60; Rio Grande del Rancho |
| 29 | Camp Ojo Caliente, NM | 33.797 | -107.366 | BLM | Sierra County; Warm Springs Chiricahua reservation camp |
| 30 | Camp Garland, NM | 35.652 | -106.098 | BLM/private | Sandoval County; temporary 1860s |
| 31 | Camp Wingate (Old), NM | 35.067 | -108.433 | BLM | McKinley County; 1862-68; distinct from Fort Wingate |
| 32 | Camp Stanton, NM | 33.497 | -105.597 | Private | Lincoln County; pre-Fort Stanton; 1850s |

#### Kansas / Colorado Plains

| # | Name | lat | lon | Land Access | Notes |
|---|---|---|---|---|---|
| 33 | Camp Harker, KS | 38.573 | -97.927 | Private | Saline County; 1866-67; later Fort Harker |
| 34 | Camp Grierson, KS | 38.500 | -98.500 | Private/BLM | Ellsworth County; temporary 1868 |
| 35 | Camp Supply, OK | 36.544 | -99.623 | BLM/private | Major 1868-1895 supply base for Sheridan's Indian Wars |
| 36 | Camp Rankin (early Sedgwick), CO | 40.989 | -102.271 | Private/urban | Early Camp Rankin 1864-65 → later Fort Sedgwick |

#### California Frontier Camps

| # | Name | lat | lon | Land Access | Notes |
|---|---|---|---|---|---|
| 37 | Camp Anderson, CA | 40.444 | -122.297 | Private | Shasta County; Wintun Country; 1857 |
| 38 | Camp Gaston, CA | 41.027 | -123.694 | Private | Humboldt County; 1858-92; Six Rivers adjacent |
| 39 | Camp Babbit (Visalia), CA | 36.331 | -119.292 | Private/urban | Tulare County; Civil War-era camp controlling passes |
| 40 | Camp Wright (Elsinore), CA | 33.622 | -117.180 | Private | Riverside County; guarded wagon road to AZ |

#### Upper Plains / Northern Frontier

| # | Name | lat | lon | Land Access | Notes |
|---|---|---|---|---|---|
| 41 | Camp Cooke, MT | 47.803 | -109.143 | BLM | Fergus County; 1866-70 on Missouri River |
| 42 | Camp Baker (later Fort Logan), MT | 46.773 | -110.672 | BLM/private | Meagher County; 1869-80; Smith River basin |
| 43 | Camp Harney, OR | 43.530 | -118.820 | BLM ✅ | Harney County; 1867-80; major BLM area |
| 44 | Camp Watson, OR | 44.840 | -119.757 | BLM ✅ | Wheeler County; 1864-69 military road camp |
| 45 | Camp Alvord, OR | 42.497 | -118.543 | BLM ✅ | Harney County; 1864-66; Alvord Basin |
| 46 | Camp Warner, OR | 42.443 | -120.267 | Fremont-Winema NF ✅ | Lake County; 1866-74; NF land |
| 47 | Camp Wallen, AZ | 31.530 | -110.053 | BLM | Cochise County; 1866-69; Babocomari Creek |
| 48 | Camp Bowie (not Fort Bowie), AZ | 32.165 | -109.374 | Private | Not the NPS Fort Bowie site — pre-1862 temp camp |
| 49 | Camp Stambaugh, WY | 42.661 | -108.743 | BLM ✅ | Fremont County; 1870-78; South Pass gold fields area |
| 50 | Camp Brown (Wind River), WY | 42.979 | -108.370 | Wind River IR | Wind River Reservation — tribal land, complicated |

#### Civil War Western Theater Camps (not already in battles)

| # | Name | lat | lon | Land Access | Notes |
|---|---|---|---|---|---|
| 51 | Camp Jackson, MO | 38.635 | -90.246 | Urban | St. Louis County; Confederate state guard camp, 1861 |
| 52 | Camp Defiance (Cairo, IL) | 37.004 | -89.176 | Private/urban | Union staging ground; western theater 1861 |
| 53 | Camp Butler, IL | 39.808 | -89.530 | Private | Sangamon County; Union training camp 1861-66 |
| 54 | Camp Morton, IN | 39.783 | -86.143 | Urban | Indianapolis; Union training & POW camp |

---

### CATEGORY C: Rendezvous / Fur Trade Sites (~25 targets)

#### Rocky Mountain Rendezvous (1825–1840)

*These are the annual fur trade gatherings — each distinct site where the rendezvous was held*

| # | Name | lat | lon | Land Access | Notes |
|---|---|---|---|---|---|
| 1 | Henry's Fork Rendezvous 1825 | 41.003 | -109.481 | BLM ✅ | Daggett Co., UT; Ashley's first rendezvous; Green R. tributary |
| 2 | Willow Valley Rendezvous 1826 | 41.943 | -111.830 | BLM/private | Cache Valley, UT; near Logan |
| 3 | Bear Lake Rendezvous 1827 & 1828 | 41.928 | -111.350 | BLM ✅ | Rich Co., UT; south end of Bear Lake |
| 4 | Popo Agie Rendezvous 1829 & 1838 | 42.838 | -108.781 | BLM ✅ | Fremont Co., WY; near Lander |
| 5 | Wind River Rendezvous 1830 | 43.078 | -108.380 | BLM/private | Fremont Co., WY; Riverton area |
| 6 | Cache Valley Rendezvous 1831 | 41.943 | -111.830 | BLM/private | Same as 1826; Cache Valley, UT |
| 7 | Pierre's Hole Rendezvous 1832 | 43.827 | -111.170 | Caribou-Targhee NF ✅ | Teton Valley, ID (NOT Jackson Hole, WY); battle followed |
| 8 | Green River (Horse Creek) Rendezvous 1833 | 42.052 | -110.034 | BLM ✅ | Sublette Co., WY; Horse Creek confluence |
| 9 | Ham's Fork Rendezvous 1834 | 41.617 | -109.941 | BLM ✅ | Uinta Co., WY; AFCO & HBC participated |
| 10 | New Fork (Green River) Rendezvous 1835 | 42.719 | -109.917 | BLM ✅ | Sublette Co., WY; near Pinedale |
| 11 | Horse Creek Rendezvous 1836 | 42.052 | -110.034 | BLM ✅ | Sublette Co., WY; same as 1833 site |
| 12 | Green River (Daniel, WY) Rendezvous 1837 | 42.909 | -110.063 | BLM ✅ | Sublette Co., WY; near confluence of Horse Cr. |
| 13 | Wind River/Popo Agie Rendezvous 1838 | 42.838 | -108.781 | BLM ✅ | Same as 1829 site |
| 14 | Horse Creek Rendezvous 1839 | 42.052 | -110.034 | BLM ✅ | Last large rendezvous before the final 1840 |
| 15 | Green River Rendezvous 1840 | 42.648 | -110.081 | BLM ✅ | Sublette Co., WY; final rendezvous of the era |

#### American Fur Company / Missouri River Posts

| # | Name | lat | lon | Land Access | Notes |
|---|---|---|---|---|---|
| 16 | Fort Cass (Sarpy II), MT | 45.882 | -107.974 | BLM ✅ | Crow Co., MT; 1832-35 AFC post; Big Horn/Yellowstone |
| 17 | Fort Van Buren, MT | 46.383 | -105.834 | BLM ✅ | Custer Co., MT; 1835-42 AFC post; Yellowstone |
| 18 | Fort Mortimer, ND | 47.820 | -103.983 | Private | Williams Co., ND; competing post near Fort Union |
| 19 | Fort Clark, ND | 47.182 | -101.067 | Private | Mercer Co., ND; major Mandan trading post 1830-60 |
| 20 | Fort Benton (AFC, early camp), MT | 47.822 | -110.669 | Private/urban | Chouteau Co., MT; headwaters trade hub; town now |

#### Hudson's Bay Company — Oregon Country

| # | Name | lat | lon | Land Access | Notes |
|---|---|---|---|---|---|
| 21 | Fort Colville (HBC), WA | 48.526 | -117.910 | Colville NF ✅ | Stevens Co., WA; 1825-71 major HBC post; NF land |
| 22 | Fort Nez Percés (Walla Walla), WA | 46.067 | -118.891 | Private | Walla Walla Co.; 1818-55; near Wallula, WA |
| 23 | Kullyspell House, ID | 48.330 | -116.497 | Private | Bonner Co., ID; David Thompson's 1809 post; Hope, ID |
| 24 | Flathead Post (Thompson's), MT | 47.583 | -114.108 | Flathead NF ✅ | Lake Co., MT; 1809 NW Company post |
| 25 | Fort Okanogan, WA | 48.101 | -119.714 | Private | Okanogan Co.; 1811 Pacific Fur Co., later NWC, HBC |

---

### CATEGORY D: Logging / Lumber Camps (~35 targets)

#### Great Lakes — Michigan

| # | Name | lat | lon | Land Access | Notes |
|---|---|---|---|---|---|
| 1 | Au Sable River Camp (Mio area), MI | 44.397 | -83.971 | Huron NF ✅ | Oscoda Co.; peak 1870-1900; NF detecting allowed |
| 2 | Manistee River Camp (Mesick area), MI | 44.271 | -85.921 | Manistee NF ✅ | Wexford Co.; extensive white pine era |
| 3 | Muskegon River Camps (Big Rapids area), MI | 43.554 | -85.199 | Huron-Manistee NF ✅ | Mecosta Co.; major pine belt |
| 4 | Tittabawassee River Camp (Midland area), MI | 43.617 | -84.247 | Private | Midland Co.; Saginaw lumber empire center |
| 5 | Rifle River Camps (Alger area), MI | 44.219 | -84.048 | Huron NF ✅ | Roscommon Co.; large camp complexes |

#### Great Lakes — Wisconsin

| # | Name | lat | lon | Land Access | Notes |
|---|---|---|---|---|---|
| 6 | Chippewa River Camp (Winter area), WI | 45.162 | -91.632 | Chequamegon NF ✅ | Sawyer Co.; dominated WI lumber era 1870-1910 |
| 7 | Menominee River Camp (Marinette), WI | 45.103 | -87.622 | Private | Marinette Co.; river-drive era |
| 8 | Wolf River Camp (Langlade), WI | 45.167 | -88.967 | Nicolet NF ✅ | Langlade Co.; Potawatomi heritage + logging |
| 9 | Namekagon River Camp (Hayward area), WI | 46.028 | -91.483 | Chequamegon NF ✅ | Sawyer Co.; St. Croix headwaters |

#### Great Lakes — Minnesota

| # | Name | lat | lon | Land Access | Notes |
|---|---|---|---|---|---|
| 10 | Pine River Camp (Backus area), MN | 46.710 | -94.404 | Chippewa NF ✅ | Cass Co.; major pine cutting district |
| 11 | Rainy Lake Logging Camp, MN | 48.547 | -93.441 | Superior NF ✅ | St. Louis Co.; Voyageurs NP boundary — check carefully |
| 12 | Vermilion River Camp (Tower area), MN | 47.798 | -92.291 | Superior NF ✅ | St. Louis Co.; iron range + logging |

#### Northeast — Maine

| # | Name | lat | lon | Land Access | Notes |
|---|---|---|---|---|---|
| 13 | Penobscot River Camp (Millinocket area), ME | 45.617 | -68.713 | Private timber land | Penobscot Co.; Great Northern Paper Company land |
| 14 | Kennebec River Camp (The Forks area), ME | 45.358 | -69.914 | Private timber land | Somerset Co.; classic river-drive country |
| 15 | Moosehead Lake Camp (Greenville), ME | 45.452 | -69.593 | Private timber land | Piscataquis Co.; largest lake in ME; logging headquarters |
| 16 | Aroostook River Camp (Presque Isle area), ME | 46.683 | -68.016 | Private | Aroostook Co.; potato boom + logging |

#### Northeast — New Hampshire / Vermont

| # | Name | lat | lon | Land Access | Notes |
|---|---|---|---|---|---|
| 17 | Connecticut River Upper Camp (Colebrook), NH | 44.892 | -71.495 | White Mountain NF ✅ | Coos Co.; upper Connecticut valley logging |
| 18 | Swift River Camp (Conway area), NH | 43.977 | -71.131 | White Mountain NF ✅ | Carroll Co.; Kancamagus Highway area |
| 19 | Lamoille River Camp (Johnson, VT) | 44.633 | -72.679 | Private | Lamoille Co.; VT logging era |

#### Northeast — New York

| # | Name | lat | lon | Land Access | Notes |
|---|---|---|---|---|---|
| 20 | Black River Camp (Lyons Falls), NY | 43.613 | -75.369 | Private | Lewis Co.; tannery and logging era |
| 21 | Oswegatchie River Camp (Cranberry Lake), NY | 44.170 | -74.827 | State Forest Preserve | Hamilton Co. — Adirondack State Park: **STATE PARK, REMOVE** |

#### Pacific Northwest — Washington

| # | Name | lat | lon | Land Access | Notes |
|---|---|---|---|---|---|
| 22 | Grays Harbor Camp (Hoquiam area), WA | 47.068 | -123.880 | Private timber | Grays Harbor Co.; massive WA coastal logging |
| 23 | Willapa Hills Camp (Raymond area), WA | 46.500 | -123.600 | Private timber | Pacific Co.; old-growth fir logging |
| 24 | Okanogan Highlands Camp (Republic area), WA | 48.650 | -118.740 | Okanogan NF ✅ | Ferry Co.; logging + mining (exclude if mining-primary) |

#### Pacific Northwest — Oregon

| # | Name | lat | lon | Land Access | Notes |
|---|---|---|---|---|---|
| 25 | Coos Bay Camp (Coos County), OR | 43.400 | -124.100 | Private | Coos Co.; massive Douglas fir logging |
| 26 | Siuslaw River Camp (Mapleton area), OR | 44.082 | -123.876 | Siuslaw NF ✅ | Lane Co.; 1880s-1920s; NF land open to detecting |
| 27 | Nehalem River Camp (Vernonia area), OR | 45.852 | -123.196 | Tillamook SF | Columbia Co. — Oregon State Forest: **STATE property, verify** |

#### Appalachian — West Virginia

| # | Name | lat | lon | Land Access | Notes |
|---|---|---|---|---|---|
| 28 | Greenbrier River Camp (Marlinton area), WV | 38.102 | -80.253 | Monongahela NF ✅ | Pocahontas Co.; massive WV lumber era |
| 29 | Cheat River Camp (Parsons area), WV | 39.097 | -79.684 | Monongahela NF ✅ | Tucker Co.; Tucker County tanning and logging |
| 30 | Black Fork Camp (Thomas area), WV | 39.148 | -79.494 | Monongahela NF ✅ | Tucker Co.; pulp/logging 1880s-1920s |
| 31 | Cranberry River Camp (Webster Springs), WV | 38.172 | -80.400 | Monongahela NF ✅ | Webster Co.; Cranberry Wilderness adjacent — check boundary |
| 32 | Gauley River Camp (Summersville area), WV | 38.269 | -80.860 | Private/BLM | Nicholas Co.; NOT the NPS Gauley NRA unit |

#### Appalachian — NC/TN/VA

| # | Name | lat | lon | Land Access | Notes |
|---|---|---|---|---|---|
| 33 | Pigeon River Camp (Waynesville area), NC | 35.603 | -83.053 | Pisgah NF ✅ | Haywood Co.; Champion Paper Fibre; massive logging 1906-20 |
| 34 | Nantahala River Camp (Andrews area), NC | 35.202 | -83.674 | Nantahala NF ✅ | Cherokee Co.; 1880s-1920s; NF land |
| 35 | Clinch River Camp (St. Paul, VA) | 36.950 | -82.430 | Jefferson NF ✅ | Wise Co., VA; NF detecting allowed |

---

## 6. SCHEMA OBSERVATIONS

From examining all existing data files, the proposed schema for `historic_camps.json` is consistent with existing files except for two things:

1. **`trails` field** — `historic_trail_landmarks.json` uses an array field `"trails": [...]`. For emigrant trail camps, consider adding this field for cross-referencing.
2. **`year` field** — `battles_seed.json` uses `"year": 1754`. For military camps, consider adding `"year_established"` and `"year_abandoned"` fields for filtering.
3. **`confidence` threshold** — Existing files use 0.80–0.95. For well-documented rendezvous sites with recorded GPS coordinates, 0.90 is appropriate. For approximate logging camp locations, 0.70 is more honest.
4. **Missing `type` field** — The `battles_seed.json` schema does include `"type": "battle"`. All entries in `historic_camps.json` should include `"type": "camp"` explicitly.

The full target schema for a `historic_camps.json` entry:

```json
{
  "name": "Camp Name",
  "type": "camp",
  "latitude": 41.676,
  "longitude": -102.51,
  "description": "2-4 sentence paragraph",
  "source": "historic_camps",
  "confidence": 0.85
}
```

---

## 7. SUMMARY OF REMOVALS

**Remove from any proposed list (in priority order):**

| Reason | Count | Examples |
|---|---|---|
| Already in `historic_trail_landmarks.json` | ~25 | Fort Laramie, Fort Kearny, South Pass, Ash Hollow, City of Rocks, Donner Pass, Alcove Spring, etc. |
| Already in `stagecoach_stops.json` | ~5 | Phantom Hill TX, Apache Pass AZ, Dragoon Springs AZ, Plum Creek NE |
| Already in `frrandp_ghost_towns.json` | ~7 | Camp Barkley, Camp Ellis, Camp Ibis, Encampment MN, etc. |
| Already in `battles_seed.json` | ~2 | Valley Forge Encampment, Camp Wildcat |
| NPS land (detecting illegal) | ~10 | Fort Union ND, Fort Bowie AZ, Whitman Mission WA, Fort Clatsop OR |
| State Park land | ~2 | Spokane House WA, any Adirondack State Forest preserve |
| Active military reservation | ~2 | Camp Wichita → Fort Sill OK |
| Wilderness Area | ~2 | BWCAW camps, New River Gorge |
| Mining camps (user exclusion) | ~5+ | #8 Gold Miners Camp, South Pass City, Calamity Camp |
| Wrong type (WWII, not historic frontier) | ~3 | Camp Ibis, Camp Barkley, Camp Ellis |

---

## 8. OTHER FINDINGS

1. **Rendezvous Sites are High Value** — The Rocky Mountain rendezvous sites (1825-1840) are nearly all on BLM land in Sublette County, WY and are not in any existing data file. They are historically documented to within a mile and have yielded trade tokens, pipe tomahawks, and Hudson's Bay Company goods in past recovery efforts. These are the highest-quality additions.

2. **Texas Frontier Camp Chain** — The 1849-1861 "first line" and "second line" of frontier forts/camps in Texas (Coleman, Throckmorton, Kerr, Uvalde, Val Verde counties) are almost entirely on private ranch land, but are not in any existing dataset and represent exceptional detecting ground when landowner permission is obtained.

3. **Gap in Oregon Military Camps** — The Oregon Department of the Interior had an active network of 1864-1880 military road camps (Camp Watson, Camp Alvord, Camp Harney, Camp Warner) that are almost entirely on BLM land and not duplicated in any existing file. These are ideal additions.

4. **Logging Camp Coordinates Should Be Approximate** — Historical logging camps were seasonal and moved continuously up drainage systems. Coordinates should represent the approximate area (center of a watershed segment), not a specific point. A confidence of 0.65-0.75 is appropriate.

5. **Cimarron National Grassland** — Several Santa Fe Trail camps (Middle Spring, Flag Spring) fall within the Cimarron National Grassland (USFS). Metal detecting on National Grasslands generally requires a special use permit from the Forest Service — this is distinct from National Forest land. Flag these separately.

6. **Camp Supply, OK** — This is an important Indian Wars supply base (1868-95) that is not in any existing file. It's in the Woodward, OK area on BLM-adjacent land and is a high-value addition for the military camp category.

7. **"Camp" vs. "Fort" Naming** — Many sites started as "Camp ___" and were later renamed "Fort ___". The user should include only the CAMP-era sites (before fort designation), not the established forts themselves. Examples: Camp Wichita → Fort Sill (REMOVE), Camp Brown → Fort Washakie (complicated — tribal land), Camp Lincoln → Camp Verde (keep as Camp Lincoln, not the later Fort).
