"""
One-time migration script: re-classify historical locations that were stored
with generic types before the more specific type values were added.

Usage (from the backend directory):
    cd backend
    python scripts/fix_location_types.py
"""

import asyncio
import sys
import os

# Allow imports from the backend package when running as a standalone script.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncpg
from app.config import settings


# Rules applied in order.  Each entry is:
#   (new_type, where_clause, description)
# The WHERE clause uses $1 as a placeholder for the list of generic types that
# are eligible for reclassification (passed as a PostgreSQL array).
RULES = [
    (
        "mission",
        (
            "(source LIKE '%mission%' OR name ILIKE '%mission%' OR name ILIKE '%iglesia%')"
            " AND type = ANY($1)"
        ),
    ),
    (
        "trading_post",
        (
            "(source LIKE '%trading_post%' OR name ILIKE '%trading post%' OR name ILIKE '%fur trade%')"
            " AND type = ANY($1)"
        ),
    ),
    (
        "ferry",
        (
            "(source LIKE '%ferr%' OR name ILIKE '%ferry%' OR name ILIKE '%crossing%')"
            " AND type = ANY($1)"
        ),
    ),
    (
        "stagecoach_stop",
        (
            "(source LIKE '%stagecoach%' OR name ILIKE '%stagecoach%' OR name ILIKE '%stage stop%')"
            " AND type = ANY($1)"
        ),
    ),
    (
        "shipwreck",
        (
            "(source LIKE '%shipwreck%' OR name ILIKE '%shipwreck%' OR name ILIKE '%wreck%')"
            " AND type = ANY($1)"
        ),
    ),
    (
        "cemetery",
        (
            "(source LIKE '%cemetery%' OR name ILIKE '%cemetery%' OR name ILIKE '%burial%'"
            " OR name ILIKE '%graveyard%')"
            " AND type = ANY($1)"
        ),
    ),
    (
        "pony_express",
        (
            "(source LIKE '%pony_express%' OR name ILIKE '%pony express%')"
            " AND type = ANY($1)"
        ),
    ),
    (
        "church",
        (
            "(source LIKE '%church%' OR name ILIKE '%church%' OR name ILIKE '%chapel%')"
            " AND type = ANY($1)"
        ),
    ),
    (
        "school",
        (
            "(source LIKE '%school%' OR name ILIKE '%school%' OR name ILIKE '%college%')"
            " AND type = ANY($1)"
        ),
    ),
    (
        # Fort -> structure: applies even when type is already 'structure' (no-op).
        "structure",
        (
            "(source LIKE '%fort%' OR name ILIKE '%fort %' OR name ILIKE '% fort')"
            " AND type = ANY($1)"
        ),
    ),
    (
        # Mine rule also covers rows currently typed as 'event'.
        "mine",
        (
            "(source LIKE '%mine%' OR name ILIKE '%mine%' OR name ILIKE '%mining%'"
            " OR name ILIKE '%lode%')"
            " AND type = ANY($1)"
        ),
    ),
]

# Generic types that are eligible for reclassification.
GENERIC_TYPES = ["event", "locale", "structure", "trail", "town"]

# The mine rule additionally covers 'event' (already included in GENERIC_TYPES).
# The fort -> structure rule is a no-op when type is already 'structure'
# (also already included).


def _asyncpg_dsn(database_url: str) -> str:
    """Convert a SQLAlchemy-style URL to a plain asyncpg DSN."""
    return database_url.replace("postgresql+asyncpg://", "postgresql://", 1)


async def main() -> None:
    dsn = _asyncpg_dsn(settings.DATABASE_URL)
    print("Fixing location types in database...")

    conn = await asyncpg.connect(dsn)
    try:
        total = 0
        for new_type, where_clause in RULES:
            # $1 = generic_types array, $2 = new_type string
            sql = f"UPDATE locations SET type = $2 WHERE {where_clause}"
            result = await conn.execute(sql, GENERIC_TYPES, new_type)
            # result is a string like "UPDATE 42"
            count = int(result.split()[-1])
            total += count
            print(f"  {new_type:<20s} {count:>4d} rows updated")

        print(f"Done. Total: {total} rows updated.")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
