#!/usr/bin/env python3
"""
Prescia Maps — Badge Seed Script

Populates the ``badges`` table with the 15 achievement badge definitions
that correspond to the PNG files in /Badges/.

Usage::

    python scripts/seed_badges.py
    python scripts/seed_badges.py --dry-run
"""

from __future__ import annotations

import asyncio
import sys
import uuid
from pathlib import Path

# Allow imports from the backend package
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import AsyncSessionLocal, Badge


BADGES = [
    # ── Hunt Milestones ──────────────────────────────────────────────────────
    {
        "badge_id": "B2FEDF50-DAE4-48D5-847D-966F94552CDA",
        "name": "First Strike",
        "description": "Log your very first metal detecting hunt.",
        "category": "hunt_milestone",
        "criteria": {"type": "hunt_count", "threshold": 1},
        "points": 10,
        "rarity": "common",
    },
    {
        "badge_id": "E4701C4C-8126-4BE7-BAA2-91B76ACE0022",
        "name": "Trailblazer",
        "description": "Log 10 metal detecting hunts.",
        "category": "hunt_milestone",
        "criteria": {"type": "hunt_count", "threshold": 10},
        "points": 25,
        "rarity": "uncommon",
    },
    {
        "badge_id": "DB6EAF3C-374D-4F89-8844-8DEDFDD824E0",
        "name": "Field Veteran",
        "description": "Log 50 metal detecting hunts.",
        "category": "hunt_milestone",
        "criteria": {"type": "hunt_count", "threshold": 50},
        "points": 50,
        "rarity": "rare",
    },
    {
        "badge_id": "E6F0E042-9E9B-4BE5-972C-FBAB71BE989D",
        "name": "Century Detectorist",
        "description": "Log 100 metal detecting hunts.",
        "category": "hunt_milestone",
        "criteria": {"type": "hunt_count", "threshold": 100},
        "points": 100,
        "rarity": "epic",
    },
    {
        "badge_id": "9994C625-AD5D-43C8-A1A4-7F044B7228AB",
        "name": "Master Detectorist",
        "description": "Log 500 metal detecting hunts.",
        "category": "hunt_milestone",
        "criteria": {"type": "hunt_count", "threshold": 500},
        "points": 250,
        "rarity": "legendary",
    },
    # ── Finds ────────────────────────────────────────────────────────────────
    {
        "badge_id": "0F708ADA-DB26-4ABB-9328-7A732ADEBA04",
        "name": "First Dig",
        "description": "Record your very first find.",
        "category": "finds",
        "criteria": {"type": "finds_count", "threshold": 1},
        "points": 10,
        "rarity": "common",
    },
    {
        "badge_id": "0202D7C9-D71B-4159-AA06-5E8909AB1579",
        "name": "Lucky Strike",
        "description": "Record 50 total finds.",
        "category": "finds",
        "criteria": {"type": "finds_count", "threshold": 50},
        "points": 30,
        "rarity": "uncommon",
    },
    {
        "badge_id": "A0160651-5B6F-40C8-A72D-C8C49796ED63",
        "name": "Gold Rush",
        "description": "Record 250 total finds.",
        "category": "finds",
        "criteria": {"type": "finds_count", "threshold": 250},
        "points": 75,
        "rarity": "rare",
    },
    {
        "badge_id": "54BC557C-A1C3-44FE-9956-B192EE1E9DF6",
        "name": "Treasure Vault",
        "description": "Record 1000 total finds.",
        "category": "finds",
        "criteria": {"type": "finds_count", "threshold": 1000},
        "points": 200,
        "rarity": "legendary",
    },
    # ── Historic Sites ───────────────────────────────────────────────────────
    {
        "badge_id": "E883C4AC-C15B-4E59-97D3-598D42EC9719",
        "name": "Battlefield Relic Hunter",
        "description": "Detect at a historic battle site.",
        "category": "sites",
        "criteria": {"type": "site_type", "site_type": "battle"},
        "points": 50,
        "rarity": "rare",
    },
    {
        "badge_id": "8B8C83CF-AA55-4E8F-BC58-F9F8E08B4FBA",
        "name": "Boomtown Prospector",
        "description": "Detect at a historic mining town.",
        "category": "sites",
        "criteria": {"type": "site_type", "site_type": "mine"},
        "points": 40,
        "rarity": "uncommon",
    },
    {
        "badge_id": "29EC28F1-A34A-41E3-B0D6-FFF06FBC6394",
        "name": "Stagecoach Chaser",
        "description": "Detect at a historic stagecoach stop.",
        "category": "sites",
        "criteria": {"type": "site_type", "site_type": "stagecoach_stop"},
        "points": 50,
        "rarity": "rare",
    },
    {
        "badge_id": "346E9135-22D6-4197-9281-D939E8F2DC51",
        "name": "Pony Express Rider",
        "description": "Detect along a historic Pony Express route.",
        "category": "sites",
        "criteria": {"type": "site_type", "site_type": "pony_express"},
        "points": 60,
        "rarity": "epic",
    },
    {
        "badge_id": "FF2299B5-FAD9-4EED-9352-DD8F9D607174",
        "name": "Mission Seeker",
        "description": "Detect near a historic mission.",
        "category": "sites",
        "criteria": {"type": "site_type", "site_type": "mission"},
        "points": 50,
        "rarity": "rare",
    },
    # ── Score ────────────────────────────────────────────────────────────────
    {
        "badge_id": "853EAE0F-736C-4CAA-B20A-3EC222CE482F",
        "name": "Prime Territory",
        "description": "Query a location with a score of 90 or higher.",
        "category": "score",
        "criteria": {"type": "score_threshold", "threshold": 90},
        "points": 75,
        "rarity": "epic",
    },
    # ── Score (second slot kept for future expansion) ─────────────────────
    # The problem statement lists 16 badges but only provides 15 UUIDs + one
    # score badge.  The 16th PNG is the second score badge placeholder.
]


async def seed(dry_run: bool = False) -> None:
    async with AsyncSessionLocal() as session:
        inserted = 0
        skipped = 0
        for spec in BADGES:
            existing = await session.execute(
                select(Badge).where(Badge.badge_id == spec["badge_id"])
            )
            if existing.scalar_one_or_none() is not None:
                skipped += 1
                continue

            badge = Badge(
                id=uuid.uuid4(),
                badge_id=spec["badge_id"],
                name=spec["name"],
                description=spec["description"],
                category=spec["category"],
                criteria=spec["criteria"],
                points=spec["points"],
                rarity=spec["rarity"],
            )
            if not dry_run:
                session.add(badge)
            inserted += 1

        if not dry_run:
            await session.commit()

        action = "Would insert" if dry_run else "Inserted"
        print(f"{action} {inserted} badge(s), skipped {skipped} existing.")


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    asyncio.run(seed(dry_run=dry_run))
