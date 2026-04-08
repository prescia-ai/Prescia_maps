#!/usr/bin/env python3
"""
Prescia Maps — Database Reset Script

Clears all data from the database so scrapers can be run fresh.

Usage::

    # Show what would be deleted (dry run — no changes made)
    python scripts/reset_db.py

    # Actually clear everything
    python scripts/reset_db.py --yes

    # Clear only specific tables
    python scripts/reset_db.py --yes --tables locations linear_features
"""

from __future__ import annotations

import argparse
import asyncio
import io
import sys

# Force UTF-8 output on Windows to prevent emoji/unicode crashes
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
if sys.stderr.encoding != 'utf-8':
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

# ---------------------------------------------------------------------------
# Bootstrap: add backend to sys.path so app.* imports work
# ---------------------------------------------------------------------------
_SCRIPT_DIR = Path(__file__).resolve().parent
_BACKEND_DIR = _SCRIPT_DIR.parent / "backend"
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from app.config import settings  # noqa: E402

# ---------------------------------------------------------------------------
# Table configuration
# ---------------------------------------------------------------------------

# Required tables — always included unless --tables overrides them
REQUIRED_TABLES = ["locations", "linear_features"]

# Optional tables — included when present; silently skipped when absent
OPTIONAL_TABLES = ["land_access_cache", "land_access_overrides"]

ALL_DEFAULT_TABLES = REQUIRED_TABLES + OPTIONAL_TABLES

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

BOX_WIDTH = 44  # inner width (between │ and │)


def _box_line(content: str, width: int = BOX_WIDTH) -> str:
    """Left-pad content inside a box row."""
    return f"║  {content:<{width - 2}}║"


def _separator(width: int = BOX_WIDTH) -> str:
    return "╠" + "═" * (width + 2) + "╣"


def _top(width: int = BOX_WIDTH) -> str:
    return "╔" + "═" * (width + 2) + "╗"


def _bottom(width: int = BOX_WIDTH) -> str:
    return "╚" + "═" * (width + 2) + "╝"


def _validate_table_name(table: str) -> None:
    """Raise ValueError if *table* contains characters that could allow SQL injection."""
    import re
    if not re.fullmatch(r"[a-zA-Z_][a-zA-Z0-9_]*", table):
        raise ValueError(
            f"Invalid table name '{table}': only letters, digits, and underscores are allowed."
        )


async def get_row_count(conn, table: str) -> int | None:
    """Return the row count for *table*, or None if the table does not exist."""
    _validate_table_name(table)
    exists_result = await conn.execute(
        text(
            "SELECT EXISTS ("
            "  SELECT 1 FROM information_schema.tables"
            "  WHERE table_schema = 'public' AND table_name = :tbl"
            ")"
        ),
        {"tbl": table},
    )
    if not exists_result.scalar():
        return None
    count_result = await conn.execute(text(f"SELECT count(*) FROM {table}"))  # noqa: S608
    return count_result.scalar()


async def truncate_table(conn, table: str) -> None:
    """TRUNCATE *table* restarting sequences and cascading to dependents."""
    _validate_table_name(table)
    await conn.execute(
        text(f"TRUNCATE TABLE {table} RESTART IDENTITY CASCADE")  # noqa: S608
    )


# ---------------------------------------------------------------------------
# Main logic
# ---------------------------------------------------------------------------


async def run(confirmed: bool, selected_tables: list[str]) -> None:
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=False,
        pool_pre_ping=True,
    )

    async with engine.begin() as conn:
        # ------------------------------------------------------------------
        # 1. Gather row counts for every requested table
        # ------------------------------------------------------------------
        counts: dict[str, int | None] = {}
        for table in selected_tables:
            counts[table] = await get_row_count(conn, table)

        # Tables that actually exist
        existing = {t: c for t, c in counts.items() if c is not None}
        total = sum(existing.values())

        # ------------------------------------------------------------------
        # 2. Print the summary box
        # ------------------------------------------------------------------
        print(_top())
        title = "Prescia Maps — Database Reset"
        print(_box_line(title))
        print(_separator())

        for table, count in counts.items():
            if count is None:
                label = f"{table}:"
                value = "(table not found)"
                row = f"{label:<26}{value:>16}"
            else:
                label = f"{table}:"
                value = f"{count:,} rows"
                row = f"{label:<26}{value:>16}"
            print(_box_line(row))

        print(_separator())
        total_row = f"{'Total:':<26}{total:,} rows{'':<5}"
        print(_box_line(total_row))
        print(_bottom())

        # ------------------------------------------------------------------
        # 3. Dry-run / confirmation gate
        # ------------------------------------------------------------------
        if not confirmed:
            print()
            print("⚠️  This will permanently delete all data above.")
            print("    Run with --yes to confirm.")
            await engine.dispose()
            return

        if not existing:
            print("\n✅ Nothing to truncate — all tables are empty or absent.")
            await engine.dispose()
            return

        print()

        # ------------------------------------------------------------------
        # 4. Truncate
        # ------------------------------------------------------------------
        for table, count in existing.items():
            await truncate_table(conn, table)
            print(f"✅ Truncated {table} ({count:,} rows removed)")

    await engine.dispose()
    print()
    print("🧹 Done. Database is clean. Run your scrapers with --fresh.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Reset the Prescia Maps database by truncating all data tables.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples:
  # Show what would be deleted (dry run — default)
  python scripts/reset_db.py

  # Actually clear everything
  python scripts/reset_db.py --yes

  # Clear only the locations table
  python scripts/reset_db.py --yes --tables locations

  # Clear only linear features
  python scripts/reset_db.py --yes --tables linear_features
""",
    )
    parser.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help="Confirm truncation. Without this flag the script is a dry run.",
    )
    parser.add_argument(
        "--tables",
        nargs="+",
        metavar="TABLE",
        default=None,
        help=(
            "Space-separated list of tables to clear. "
            f"Defaults to all tables: {', '.join(ALL_DEFAULT_TABLES)}"
        ),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.tables:
        selected = args.tables
        # Warn about unknown tables but don't abort — user may know better
        known = set(ALL_DEFAULT_TABLES)
        for t in selected:
            if t not in known:
                print(f"⚠️  '{t}' is not a recognized table name — proceeding anyway.")
    else:
        selected = list(ALL_DEFAULT_TABLES)

    asyncio.run(run(confirmed=args.yes, selected_tables=selected))


if __name__ == "__main__":
    main()
