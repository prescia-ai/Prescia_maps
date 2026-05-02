import asyncio
from sqlalchemy import text
from app.models.database import async_session

async def main():
    async with async_session() as s:
        result = await s.execute(text("""
            UPDATE locations
            SET geom = ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)
            WHERE geom IS NULL AND latitude IS NOT NULL AND longitude IS NOT NULL
        """))
        await s.commit()
        print(f"locations updated: {result.rowcount}")
asyncio.run(main())
