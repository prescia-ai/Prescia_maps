"""
Seed script for achievement badges.

Seeds all badge definitions into the ``badges`` table.
Run with:
    python scripts/seed_badges.py
"""

import asyncio
import sys
import os

# Allow importing app modules from the backend directory
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.models.database import Badge, AsyncSessionLocal, engine, create_tables


BADGES = [
    # ── Hunt Milestones ────────────────────────────────────────────────────────
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
    # ── Finds ─────────────────────────────────────────────────────────────────
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
        "description": "Record 1,000 total finds.",
        "category": "finds",
        "criteria": {"type": "finds_count", "threshold": 1000},
        "points": 200,
        "rarity": "legendary",
    },
    # ── Historic Sites ────────────────────────────────────────────────────────
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
    # ── Score ─────────────────────────────────────────────────────────────────
    {
        "badge_id": "853EAE0F-736C-4CAA-B20A-3EC222CE482F",
        "name": "Prime Territory",
        "description": "Hunt a location with an Aurik score of 90 or higher.",
        "category": "score",
        "criteria": {"type": "score_threshold", "threshold": 90},
        "points": 75,
        "rarity": "epic",
    },
    # ── Community Contribution ────────────────────────────────────────────────
    {
        "badge_id": "D764C958-9847-45D8-BEB6-3611D2545D47",
        "name": "Map Maker",
        "description": "Submit your first location to the Aurik database.",
        "category": "community",
        "criteria": {"type": "submission_count", "threshold": 1},
        "points": 20,
        "rarity": "uncommon",
    },
    {
        "badge_id": "DA31CC83-B2E7-4A1C-9705-658B35DE1C98",
        "name": "History Keeper",
        "description": "Contribute historical notes or documentation to a location.",
        "category": "community",
        "criteria": {"type": "contribution_count", "threshold": 5},
        "points": 30,
        "rarity": "rare",
    },
    {
        "badge_id": "AF7AEB2C-6F9C-4734-A537-12C0610CF212",
        "name": "Community Historian",
        "description": "Become a trusted contributor with 25+ submissions.",
        "category": "community",
        "criteria": {"type": "submission_count", "threshold": 25},
        "points": 100,
        "rarity": "epic",
    },
    # ── Social ────────────────────────────────────────────────────────────────
    {
        "badge_id": "94297D70-0BF8-4913-ADB8-073E6672EB85",
        "name": "First Shout",
        "description": "Post your first comment or share a find with the community.",
        "category": "social",
        "criteria": {"type": "comment_count", "threshold": 1},
        "points": 10,
        "rarity": "common",
    },
    {
        "badge_id": "8773F5EF-1AE8-4212-8191-479E2E78ABA8",
        "name": "Great Find!",
        "description": "Receive 10 likes or positive reactions on a shared find.",
        "category": "social",
        "criteria": {"type": "likes_count", "threshold": 10},
        "points": 25,
        "rarity": "uncommon",
    },
    {
        "badge_id": "D9A62F2B-C821-4D87-AB96-1448AD741E13",
        "name": "Crowd Favorite",
        "description": "Have one of your finds receive 50+ likes from the community.",
        "category": "social",
        "criteria": {"type": "single_post_likes", "threshold": 50},
        "points": 50,
        "rarity": "rare",
    },
    {
        "badge_id": "36FF0A6C-A14B-49C1-9183-C66A02581A26",
        "name": "Community Pillar",
        "description": "Reach 100+ total likes across all your shared content.",
        "category": "social",
        "criteria": {"type": "total_likes", "threshold": 100},
        "points": 75,
        "rarity": "epic",
    },
    # ── Score ─────────────────────────────────────────────────────────────────
    {
        "badge_id": "FC0C795B-E848-48D2-88A1-D69F7B3E3432",
        "name": "Off The Beaten Path",
        "description": "Hunt at a location with an Aurik score below 50 (high difficulty).",
        "category": "score",
        "criteria": {"type": "low_score_hunt", "threshold": 50},
        "points": 40,
        "rarity": "rare",
    },
    # ── Geographic ────────────────────────────────────────────────────────────
    {
        "badge_id": "B4ED4716-472A-423E-804D-143690D66C30",
        "name": "Multi-State Hunter",
        "description": "Log hunts in 3 or more different states.",
        "category": "geographic",
        "criteria": {"type": "states_visited", "threshold": 3},
        "points": 60,
        "rarity": "rare",
    },
]


async def seed() -> None:
    """Ensure the schema is up-to-date and insert any missing badge rows."""
    await create_tables()

    async with AsyncSessionLocal() as session:
        from sqlalchemy import select

        existing_result = await session.execute(select(Badge.badge_id))
        existing_ids = {row[0].upper() for row in existing_result.all()}

        inserted = 0
        for data in BADGES:
            if data["badge_id"].upper() in existing_ids:
                print(f"  skip  {data['name']} (already exists)")
                continue

            badge = Badge(
                badge_id=data["badge_id"],
                name=data["name"],
                description=data["description"],
                category=data["category"],
                criteria=data["criteria"],
                points=data["points"],
                rarity=data["rarity"],
            )
            session.add(badge)
            inserted += 1
            print(f"  insert {data['name']}")

        await session.commit()
        print(f"\nDone. {inserted} badge(s) inserted, {len(BADGES) - inserted} skipped.")


if __name__ == "__main__":
    asyncio.run(seed())
