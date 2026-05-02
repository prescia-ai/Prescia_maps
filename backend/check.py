import asyncio
from sqlalchemy import text
from app.models.database import async_session  # adjust import if your session helper is named differently

async def main():
    async with async_session() as s:
        total = (await s.execute(text("SELECT COUNT(*) FROM locations"))).scalar()
        geom_null = (await s.execute(text("SELECT COUNT(*) FROM locations WHERE geom IS NULL"))).scalar()
        print(f"locations total: {total}")
        print(f"locations with geom IS NULL: {geom_null}")
        feats_total = (await s.execute(text("SELECT COUNT(*) FROM linear_features"))).scalar()
        feats_null = (await s.execute(text("SELECT COUNT(*) FROM linear_features WHERE geom IS NULL"))).scalar()
        print(f"linear_features total: {feats_total}")
        print(f"linear_features with geom IS NULL: {feats_null}")

asyncio.run(main())
