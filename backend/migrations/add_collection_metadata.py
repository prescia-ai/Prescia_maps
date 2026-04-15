"""
Migration: add find_type and material columns to collection_photos.

Run with:
    python backend/migrations/add_collection_metadata.py
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import text
from app.models.database import engine


async def migrate():
    async with engine.begin() as conn:
        await conn.execute(text(
            "ALTER TABLE collection_photos ADD COLUMN IF NOT EXISTS find_type VARCHAR(50)"
        ))
        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_collection_photos_find_type ON collection_photos (find_type)"
        ))
        await conn.execute(text(
            "ALTER TABLE collection_photos ADD COLUMN IF NOT EXISTS material VARCHAR(50)"
        ))
        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_collection_photos_material ON collection_photos (material)"
        ))
    print("✅ Migration complete")


if __name__ == "__main__":
    asyncio.run(migrate())
