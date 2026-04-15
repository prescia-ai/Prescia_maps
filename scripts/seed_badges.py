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
        "name": "Distance Hunter",
        "description": "Travel 500 km or more to metal detecting sites.",
        "category": "geographic",
        "criteria": {"type": "max_distance_traveled", "threshold": 500},
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
        "description": "Have 25 submissions approved by the community.",
        "category": "community",
        "criteria": {"type": "approved_submissions", "threshold": 25},
        "points": 75,
        "rarity": "rare",
    },
    {
        "badge_id": "AF7AEB2C-6F9C-4734-A537-12C0610CF212",
        "name": "Community Historian",
        "description": "Have 100 submissions approved by the community.",
        "category": "community",
        "criteria": {"type": "approved_submissions", "threshold": 100},
        "points": 200,
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
        "name": "Route Seeker",
        "description": "Hunt within 100 meters of a historic trail.",
        "category": "sites",
        "criteria": {"type": "linear_feature_proximity", "feature_type": "trail", "distance_meters": 100},
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
    # ── Geographic / Streak ─────────────────────────────────────────────────────
    {
        "badge_id": "BD2EEC79-E66D-4B67-B558-7AE288CFD347",
        "name": "Weekend Warrior",
        "description": "Log hunts on consecutive weekend days.",
        "category": "geographic",
        "criteria": {"type": "weekend_streak", "threshold": 2},
        "points": 30,
        "rarity": "uncommon",
    },
    {
        "badge_id": "EFEECA8E-48D2-47A5-BB32-5055E480C14D",
        "name": "Seasonal Hunter",
        "description": "Log hunts during all four seasons in a single year.",
        "category": "geographic",
        "criteria": {"type": "seasonal_coverage", "threshold": 4},
        "points": 50,
        "rarity": "rare",
    },
    {
        "badge_id": "54F64423-B215-479E-897B-28C78EE4FC2E",
        "name": "Year-Long Detectorist",
        "description": "Log at least one hunt every month for an entire year.",
        "category": "geographic",
        "criteria": {"type": "monthly_streak", "threshold": 12},
        "points": 100,
        "rarity": "epic",
    },
    # ── Special Event ────────────────────────────────────────────────────────────
    {
        "badge_id": "8EDC9DC3-02FE-4E5F-9B75-DBD39ECB2527",
        "name": "Night Hunter",
        "description": "Log a hunt after sunset.",
        "category": "special_event",
        "criteria": {"type": "time_of_day", "time_range": "night"},
        "points": 25,
        "rarity": "uncommon",
    },
    {
        "badge_id": "3FB6A091-CD5D-4455-8463-C2C21FDCA7D8",
        "name": "Dawn Patrol",
        "description": "Log a hunt at sunrise.",
        "category": "special_event",
        "criteria": {"type": "time_of_day", "time_range": "dawn"},
        "points": 25,
        "rarity": "uncommon",
    },
    {
        "badge_id": "86923B0E-13EA-4171-B779-9464C2B67CA2",
        "name": "Storm Chaser",
        "description": "Log a hunt during or immediately after a storm.",
        "category": "special_event",
        "criteria": {"type": "weather_condition", "condition": "storm"},
        "points": 40,
        "rarity": "rare",
    },
    {
        "badge_id": "D3DE9936-C1D5-48AD-BF33-1C0E40C314C3",
        "name": "First Snow",
        "description": "Log a hunt during the first snowfall of the year.",
        "category": "special_event",
        "criteria": {"type": "weather_condition", "condition": "first_snow"},
        "points": 30,
        "rarity": "rare",
    },
    # ── Rarity / Value ───────────────────────────────────────────────────────────
    {
        "badge_id": "061302AA-D444-4F8F-ADDC-983777155D9E",
        "name": "Silver Streak",
        "description": "Add 10 silver items to your collection.",
        "category": "treasure_trove",
        "criteria": {"type": "collection_material_count", "material": "silver", "threshold": 10},
        "points": 50,
        "rarity": "rare",
    },
    # ── Time / Dedication ────────────────────────────────────────────────────────
    {
        "badge_id": "C636E674-F8EB-48B6-913A-8ADDC228455D",
        "name": "Early Bird",
        "description": "Log 10 hunts before 8am.",
        "category": "dedication",
        "criteria": {"type": "early_hunts", "threshold": 10, "time_before": "08:00"},
        "points": 40,
        "rarity": "uncommon",
    },
    {
        "badge_id": "45234C5B-7974-4861-B3DA-895C7ACB8E92",
        "name": "Moonlighter",
        "description": "Log 10 hunts after 8pm.",
        "category": "dedication",
        "criteria": {"type": "late_hunts", "threshold": 10, "time_after": "20:00"},
        "points": 40,
        "rarity": "uncommon",
    },
    # ── Conservation ──────────────────────────────────────────────────────────────
    {
        "badge_id": "133A322B-ECBA-4BCA-9A2C-1BBF64BE34D9",
        "name": "Trash Collector",
        "description": "Remove 100 pieces of trash while metal detecting.",
        "category": "conservation",
        "criteria": {"type": "trash_collected", "threshold": 100},
        "points": 50,
        "rarity": "rare",
    },
    {
        "badge_id": "1FA4510C-7ECF-44F1-9783-C646414662DF",
        "name": "Leave No Trace",
        "description": "Fill in 50 dig holes properly.",
        "category": "conservation",
        "criteria": {"type": "holes_filled", "threshold": 50},
        "points": 60,
        "rarity": "rare",
    },
    # ── Treasure Trove ────────────────────────────────────────────────────────────
    {
        "badge_id": "A1B2C3D4-E5F6-7890-ABCD-EF1234567890",
        "name": "Coin Collector",
        "description": "Add 50 coins to your collection.",
        "category": "treasure_trove",
        "criteria": {"type": "collection_type_count", "find_type": "coin", "threshold": 50},
        "points": 60,
        "rarity": "rare",
    },
    {
        "badge_id": "B2C3D4E5-F6A7-8901-BCDE-F12345678901",
        "name": "Button Box",
        "description": "Add 25 buttons to your collection.",
        "category": "treasure_trove",
        "criteria": {"type": "collection_type_count", "find_type": "button", "threshold": 25},
        "points": 50,
        "rarity": "rare",
    },
    {
        "badge_id": "C3D4E5F6-A7B8-9012-CDEF-123456789012",
        "name": "Lead Farmer",
        "description": "Add 50 bullets to your collection.",
        "category": "treasure_trove",
        "criteria": {"type": "collection_type_count", "find_type": "bullet", "threshold": 50},
        "points": 50,
        "rarity": "rare",
    },
    {
        "badge_id": "D4E5F6A7-B8C9-0123-DEF0-234567890123",
        "name": "Jewelry Box",
        "description": "Add 10 jewelry items to your collection.",
        "category": "treasure_trove",
        "criteria": {"type": "collection_type_count", "find_type": "jewelry", "threshold": 10},
        "points": 70,
        "rarity": "epic",
    },
    {
        "badge_id": "E5F6A7B8-C9D0-1234-EF01-345678901234",
        "name": "Buckle Up",
        "description": "Add 15 buckles to your collection.",
        "category": "treasure_trove",
        "criteria": {"type": "collection_type_count", "find_type": "buckle", "threshold": 15},
        "points": 50,
        "rarity": "rare",
    },
]


async def seed() -> None:
    """Ensure the schema is up-to-date and upsert all badge rows."""
    await create_tables()

    async with AsyncSessionLocal() as session:
        from sqlalchemy import select

        existing_result = await session.execute(select(Badge))
        existing_map = {row.badge_id.upper(): row for row in existing_result.scalars().all()}

        inserted = 0
        updated = 0
        for data in BADGES:
            badge_id_upper = data["badge_id"].upper()
            if badge_id_upper in existing_map:
                badge = existing_map[badge_id_upper]
                changed = (
                    badge.name != data["name"]
                    or badge.description != data["description"]
                    or badge.category != data["category"]
                    or badge.criteria != data["criteria"]
                    or badge.points != data["points"]
                    or badge.rarity != data["rarity"]
                )
                if changed:
                    badge.name = data["name"]
                    badge.description = data["description"]
                    badge.category = data["category"]
                    badge.criteria = data["criteria"]
                    badge.points = data["points"]
                    badge.rarity = data["rarity"]
                    updated += 1
                    print(f"  update {data['name']}")
                else:
                    print(f"  skip  {data['name']} (no changes)")
            else:
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
        print(f"\nDone. {inserted} badge(s) inserted, {updated} updated, {len(BADGES) - inserted - updated} skipped.")


if __name__ == "__main__":
    asyncio.run(seed())
