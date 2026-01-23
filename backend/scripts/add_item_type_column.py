#!/usr/bin/env python3
"""
Migration script to add item_type column to auction_items table.

Usage:
    python -m scripts.add_item_type_column
"""
import asyncio
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from app.database import async_session_maker, database_url


async def add_item_type_column():
    """Add item_type column to auction_items table if it doesn't exist."""
    print("=" * 60)
    print("Adding item_type column to auction_items table")
    print("=" * 60)

    is_postgres = "postgresql" in database_url or "postgres" in database_url
    print(f"Database type: {'PostgreSQL' if is_postgres else 'SQLite'}")

    async with async_session_maker() as session:
        # Check if column already exists (different SQL for PostgreSQL vs SQLite)
        if is_postgres:
            check_query = text("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'auction_items' AND column_name = 'item_type'
            """)
            result = await session.execute(check_query)
            exists = result.fetchone() is not None
        else:
            check_query = text("PRAGMA table_info(auction_items)")
            result = await session.execute(check_query)
            columns = result.fetchall()
            exists = any(col[1] == 'item_type' for col in columns)

        if exists:
            print("\nColumn 'item_type' already exists. Nothing to do.")
            return

        print("\nAdding 'item_type' column...")

        # Add the column
        alter_query = text("""
            ALTER TABLE auction_items
            ADD COLUMN item_type VARCHAR(20)
        """)
        await session.execute(alter_query)

        # Add index for the column
        index_query = text("""
            CREATE INDEX IF NOT EXISTS ix_auction_items_item_type
            ON auction_items (item_type)
        """)
        await session.execute(index_query)

        await session.commit()
        print("Column 'item_type' added successfully with index.")
        print("\nNext step: Run 'python -m scripts.migrate_item_types' to classify existing items.")


if __name__ == "__main__":
    asyncio.run(add_item_type_column())
