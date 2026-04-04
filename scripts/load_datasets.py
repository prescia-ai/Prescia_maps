#!/usr/bin/env python3
"""
Script to load seed datasets for trails, railroads, and other historical data.
Run from project root: python scripts/load_datasets.py
"""
import asyncio
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

import uuid
from app.models.database import AsyncSessionLocal, create_tables, LinearFeature, Location, MapLayer
from geoalchemy2.shape import from_shape
from shapely.geometry import LineString, Point
from sqlalchemy import select

# Oregon Trail waypoints (approximate)
OREGON_TRAIL_COORDS = [
    (-94.5786, 39.0997),  # Independence, MO
    (-96.6753, 40.8136),  # Nebraska City, NE
    (-98.3420, 40.9248),  # Kearney, NE
    (-99.8566, 40.9248),  # North Platte, NE
    (-104.8202, 41.1400), # Scotts Bluff, NE
    (-104.8202, 42.8666), # Fort Laramie, WY
    (-107.2359, 42.8666), # South Pass, WY
    (-110.9743, 43.4799), # Fort Hall, ID
    (-116.9971, 44.0682), # Boise, ID
    (-121.8872, 45.5051), # Portland, OR
]

# Trail of Tears (approximate path)
TRAIL_OF_TEARS_COORDS = [
    (-84.3963, 33.7490),  # Atlanta, GA
    (-85.9714, 35.3670),  # Chattanooga, TN
    (-86.7816, 36.1627),  # Nashville, TN
    (-87.6298, 36.5298),  # Murray, KY
    (-89.7294, 36.3681),  # Jackson, TN
    (-90.1994, 35.1495),  # Memphis, TN
    (-91.8318, 35.2010),  # Little Rock, AR
    (-94.4132, 36.0635),  # Fayetteville, AR
    (-95.9928, 36.1540),  # Tahlequah, OK
]

# Santa Fe Trail (approximate)
SANTA_FE_TRAIL_COORDS = [
    (-94.5786, 39.0997),  # Independence, MO
    (-95.6752, 37.6922),  # Council Grove, KS
    (-97.5164, 37.8393),  # Great Bend, KS
    (-99.3268, 37.7481),  # Dodge City, KS
    (-103.8084, 37.7481), # La Junta, CO
    (-105.9378, 35.6870), # Santa Fe, NM
]

# Transcontinental Railroad (approximate)
TRANSCONTINENTAL_RR_COORDS = [
    (-95.3698, 29.7604),  # Houston (southern connection)
    (-96.7970, 32.7767),  # Dallas
    (-97.7431, 30.2672),  # Austin
    (-106.4850, 31.7619), # El Paso
    (-110.9265, 32.2217), # Tucson
    (-112.0740, 33.4484), # Phoenix
    (-117.1611, 32.7157), # San Diego
    (-118.2437, 34.0522), # Los Angeles
    (-122.4194, 37.7749), # San Francisco
]

# Historic gold rush towns
HISTORIC_TOWNS = [
    {"name": "Bodie", "lat": 38.2097, "lon": -119.0076, "year": 1859, "type": "town", "desc": "Ghost town - major gold mining boomtown in California"},
    {"name": "Virginia City, NV", "lat": 39.3097, "lon": -119.6487, "year": 1859, "type": "town", "desc": "Famous Comstock Lode silver mining town"},
    {"name": "Deadwood, SD", "lat": 44.3769, "lon": -103.7296, "year": 1876, "type": "town", "desc": "Gold rush town in the Black Hills"},
    {"name": "Tombstone, AZ", "lat": 31.7129, "lon": -110.0674, "year": 1879, "type": "town", "desc": "Silver mining boomtown, site of O.K. Corral"},
    {"name": "Central City, CO", "lat": 39.8019, "lon": -105.5133, "year": 1859, "type": "town", "desc": "Colorado gold rush town"},
    {"name": "Cripple Creek, CO", "lat": 38.7469, "lon": -105.1786, "year": 1890, "type": "mine", "desc": "Major gold mining district"},
    {"name": "Leadville, CO", "lat": 39.2508, "lon": -106.2925, "year": 1877, "type": "mine", "desc": "Silver and lead mining town at high altitude"},
    {"name": "Nevada City, CA", "lat": 39.2613, "lon": -121.0127, "year": 1849, "type": "town", "desc": "California Gold Rush town"},
    {"name": "Coloma, CA", "lat": 38.8038, "lon": -120.8910, "year": 1848, "type": "mine", "desc": "Site of first gold discovery in California"},
    {"name": "Jerome, AZ", "lat": 34.7520, "lon": -112.1138, "year": 1876, "type": "mine", "desc": "Copper mining ghost town"},
]

# Civil War battle sites
BATTLE_SITES = [
    {"name": "Battle of Gettysburg", "lat": 39.8112, "lon": -77.2253, "year": 1863, "type": "battle", "desc": "Largest battle of the Civil War, turning point"},
    {"name": "Battle of Antietam", "lat": 39.4676, "lon": -77.7454, "year": 1862, "type": "battle", "desc": "Bloodiest single day in American military history"},
    {"name": "Battle of Chickamauga", "lat": 34.9418, "lon": -85.2660, "year": 1863, "type": "battle", "desc": "Second bloodiest battle of the Civil War"},
    {"name": "Battle of Chancellorsville", "lat": 38.3051, "lon": -77.6395, "year": 1863, "type": "battle", "desc": "Confederate victory, Stonewall Jackson mortally wounded"},
    {"name": "Battle of Vicksburg", "lat": 32.3526, "lon": -90.8779, "year": 1863, "type": "battle", "desc": "Union siege that split the Confederacy"},
    {"name": "Battle of Fredericksburg", "lat": 38.3032, "lon": -77.4605, "year": 1862, "type": "battle", "desc": "Major Confederate victory"},
    {"name": "Battle of Shiloh", "lat": 35.1447, "lon": -88.3404, "year": 1862, "type": "battle", "desc": "Union victory in Tennessee"},
    {"name": "Battle of Cold Harbor", "lat": 37.6010, "lon": -77.2558, "year": 1864, "type": "battle", "desc": "Catastrophic Union assault"},
    {"name": "Battle of Bull Run (Second)", "lat": 38.8118, "lon": -77.5161, "year": 1862, "type": "battle", "desc": "Confederate victory near Manassas"},
    {"name": "Battle of Nashville", "lat": 36.1627, "lon": -86.7816, "year": 1864, "type": "battle", "desc": "Decisive Union victory"},
    {"name": "Battle of Spotsylvania", "lat": 38.2221, "lon": -77.5883, "year": 1864, "type": "battle", "desc": "Bloody battle in the Overland Campaign"},
    {"name": "Battle of Atlanta", "lat": 33.7490, "lon": -84.3880, "year": 1864, "type": "battle", "desc": "Sherman's capture of Atlanta"},
    {"name": "Battle of Petersburg", "lat": 37.2279, "lon": -77.4019, "year": 1864, "type": "battle", "desc": "Nine-month siege before war's end"},
    {"name": "Battle of Mobile Bay", "lat": 30.6954, "lon": -88.0399, "year": 1864, "type": "battle", "desc": "Damn the torpedoes - Farragut's naval battle"},
    {"name": "Battle of Perryville", "lat": 37.6568, "lon": -84.9711, "year": 1862, "type": "battle", "desc": "Largest Civil War battle in Kentucky"},
    {"name": "Battle of Wilson's Creek", "lat": 37.1140, "lon": -93.4224, "year": 1861, "type": "battle", "desc": "First major Civil War battle west of Mississippi"},
    {"name": "Battle of Fort Donelson", "lat": 36.4862, "lon": -87.8578, "year": 1862, "type": "battle", "desc": "Grant's first major victory"},
    {"name": "Battle of Stones River", "lat": 35.8890, "lon": -86.4394, "year": 1862, "type": "battle", "desc": "Winter battle near Murfreesboro, TN"},
    {"name": "Battle of Bentonville", "lat": 35.3195, "lon": -78.3283, "year": 1865, "type": "battle", "desc": "Last major Confederate offensive in the Carolinas"},
    {"name": "Battle of Fort Sumter", "lat": 32.7521, "lon": -79.8745, "year": 1861, "type": "battle", "desc": "First engagement of the Civil War"},
]

# Fort sites
FORT_SITES = [
    {"name": "Fort Laramie", "lat": 42.2133, "lon": -104.5497, "year": 1834, "type": "structure", "desc": "Key military fort on the Oregon Trail"},
    {"name": "Fort Kearny", "lat": 40.6447, "lon": -98.9956, "year": 1848, "type": "structure", "desc": "Military fort on the Oregon Trail"},
    {"name": "Fort Union", "lat": 36.3540, "lon": -104.0387, "year": 1851, "type": "structure", "desc": "Largest 19th-century military fort in the Southwest"},
    {"name": "Fort Bowie", "lat": 32.1449, "lon": -109.4387, "year": 1862, "type": "structure", "desc": "Military fort during Apache Wars"},
    {"name": "Fort Concho", "lat": 31.4551, "lon": -100.4404, "year": 1867, "type": "structure", "desc": "Buffalo Soldiers fort in West Texas"},
    {"name": "Fort Sill", "lat": 34.6494, "lon": -98.4033, "year": 1869, "type": "structure", "desc": "Military fort in Indian Territory"},
    {"name": "Fort Leavenworth", "lat": 39.3616, "lon": -94.9113, "year": 1827, "type": "structure", "desc": "Oldest active US Army post west of the Mississippi"},
    {"name": "Fort Bridger", "lat": 41.3192, "lon": -110.3880, "year": 1843, "type": "structure", "desc": "Mountain man trading post on Oregon Trail"},
    {"name": "Fort Snelling", "lat": 44.8926, "lon": -93.1805, "year": 1819, "type": "structure", "desc": "Confluence of Mississippi and Minnesota Rivers"},
    {"name": "Fort Ticonderoga", "lat": 43.8450, "lon": -73.3874, "year": 1755, "type": "structure", "desc": "French and Indian War / Revolutionary War fort"},
]

# Mining camps
MINING_CAMPS = [
    {"name": "Sutter's Mill", "lat": 38.8038, "lon": -120.8910, "year": 1848, "type": "mine", "desc": "Site of California Gold Rush discovery"},
    {"name": "Comstock Lode", "lat": 39.3097, "lon": -119.6487, "year": 1859, "type": "mine", "desc": "Major silver deposit in Nevada"},
    {"name": "Klondike Gold Fields", "lat": 64.0609, "lon": -139.4292, "year": 1896, "type": "mine", "desc": "Yukon gold rush region"},
    {"name": "Pikes Peak Gold Rush Area", "lat": 38.8409, "lon": -105.0423, "year": 1859, "type": "mine", "desc": "Colorado gold rush region"},
    {"name": "Black Hills Gold District", "lat": 44.0805, "lon": -103.2310, "year": 1874, "type": "mine", "desc": "Dakota Territory gold discovery"},
    {"name": "Bisbee Copper Mine", "lat": 31.4479, "lon": -109.9284, "year": 1880, "type": "mine", "desc": "Major copper mining district in Arizona"},
    {"name": "Butte Mining District", "lat": 46.0038, "lon": -112.5348, "year": 1864, "type": "mine", "desc": "Richest hill on earth - copper mining"},
    {"name": "Silverton, CO", "lat": 37.8122, "lon": -107.6617, "year": 1874, "type": "mine", "desc": "Silver mining town in San Juan Mountains"},
    {"name": "Park City, UT", "lat": 40.6461, "lon": -111.4980, "year": 1868, "type": "mine", "desc": "Silver mining boomtown"},
    {"name": "Globe Mining District", "lat": 33.3942, "lon": -110.7863, "year": 1876, "type": "mine", "desc": "Arizona silver and copper mining"},
]

async def insert_trail(session, name: str, coords: list, trail_type: str, source: str):
    """Insert a trail/railroad as a LinearFeature."""
    existing = await session.execute(
        select(LinearFeature).where(LinearFeature.name == name)
    )
    if existing.scalar_one_or_none():
        print(f"  Skipping {name} (already exists)")
        return False

    line = LineString(coords)
    feature = LinearFeature(
        id=uuid.uuid4(),
        name=name,
        type=trail_type,
        geom=from_shape(line, srid=4326),
        source=source
    )
    session.add(feature)
    print(f"  Added {trail_type}: {name}")
    return True

async def insert_location(session, data: dict):
    """Insert a location point."""
    existing = await session.execute(
        select(Location).where(Location.name == data['name'])
    )
    if existing.scalar_one_or_none():
        return False

    loc = Location(
        id=uuid.uuid4(),
        name=data['name'],
        type=data['type'],
        latitude=data['lat'],
        longitude=data['lon'],
        year=data.get('year'),
        description=data.get('desc', ''),
        source='seed_data',
        confidence=0.9,
        geom=from_shape(Point(data['lon'], data['lat']), srid=4326)
    )
    session.add(loc)
    return True

async def main():
    print("Creating database tables...")
    await create_tables()

    async with AsyncSessionLocal() as session:
        print("\n--- Loading Trails ---")
        await insert_trail(session, "Oregon Trail", OREGON_TRAIL_COORDS, "trail", "Historical record")
        await insert_trail(session, "Trail of Tears", TRAIL_OF_TEARS_COORDS, "trail", "Historical record")
        await insert_trail(session, "Santa Fe Trail", SANTA_FE_TRAIL_COORDS, "trail", "Historical record")
        await insert_trail(session, "Transcontinental Railroad (Southern)", TRANSCONTINENTAL_RR_COORDS, "railroad", "Historical record")

        print("\n--- Loading Historic Towns ---")
        count = 0
        for town in HISTORIC_TOWNS:
            if await insert_location(session, town):
                count += 1
        print(f"  Added {count} historic towns")

        print("\n--- Loading Battle Sites ---")
        count = 0
        for battle in BATTLE_SITES:
            if await insert_location(session, battle):
                count += 1
        print(f"  Added {count} battle sites")

        print("\n--- Loading Fort Sites ---")
        count = 0
        for fort in FORT_SITES:
            if await insert_location(session, fort):
                count += 1
        print(f"  Added {count} fort sites")

        print("\n--- Loading Mining Camps ---")
        count = 0
        for camp in MINING_CAMPS:
            if await insert_location(session, camp):
                count += 1
        print(f"  Added {count} mining camps")

        print("\n--- Loading Map Layers ---")
        layers = [
            MapLayer(
                id=uuid.uuid4(),
                name="USGS Historical Topographic Maps",
                type="usgs",
                url="https://basemap.nationalmap.gov/arcgis/rest/services/USGSTopo/MapServer/tile/{z}/{y}/{x}",
                metadata_={"description": "USGS National Map topographic tile service", "format": "tile"}
            ),
            MapLayer(
                id=uuid.uuid4(),
                name="USGS National Map",
                type="usgs",
                url="https://carto.nationalmap.gov/arcgis/rest/services/structures/MapServer/0/query?f=geojson",
                metadata_={"description": "USGS structures dataset", "format": "geojson"}
            ),
        ]
        for layer in layers:
            existing = await session.execute(
                select(MapLayer).where(MapLayer.name == layer.name)
            )
            if not existing.scalar_one_or_none():
                session.add(layer)
                print(f"  Added map layer: {layer.name}")

        await session.commit()
        print("\n✅ Seed data loaded successfully!")

if __name__ == '__main__':
    asyncio.run(main())
