import asyncio
from sqlalchemy import text
from app.models.database import AsyncSessionLocal

async def main():
    async with AsyncSessionLocal() as s:
        r = await s.execute(text("""
            UPDATE locations
            SET geom = ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)
            WHERE geom IS NULL AND latitude IS NOT NULL AND longitude IS NOT NULL
        """))
        await s.commit()
        print(f"locations updated: {r.rowcount}")

asyncio.run(main())
