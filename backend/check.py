import asyncio
from sqlalchemy import text
from app.models.database import AsyncSessionLocal

async def main():
    async with AsyncSessionLocal() as s:
        total = (await s.execute(text("SELECT COUNT(*) FROM locations"))).scalar()
        geom_null = (await s.execute(text("SELECT COUNT(*) FROM locations WHERE geom IS NULL"))).scalar()
        feats_total = (await s.execute(text("SELECT COUNT(*) FROM linear_features"))).scalar()
        feats_null = (await s.execute(text("SELECT COUNT(*) FROM linear_features WHERE geom IS NULL"))).scalar()
        print(f"locations: {total} total, {geom_null} with geom NULL")
        print(f"linear_features: {feats_total} total, {feats_null} with geom NULL")

asyncio.run(main())
