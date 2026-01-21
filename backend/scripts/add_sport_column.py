#!/usr/bin/env python3
"""
Migration script to add sport column to auction_items table.
Run this before deploying the new code.
"""
import sqlite3
import sys
from pathlib import Path

# Database path - adjust if needed
DB_PATH = Path(__file__).parent.parent / "auction_data.db"


def add_sport_column():
    """Add sport column to auction_items table if it doesn't exist"""
    print(f"Database path: {DB_PATH}")

    if not DB_PATH.exists():
        print(f"ERROR: Database not found at {DB_PATH}")
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Check if column already exists
        cursor.execute("PRAGMA table_info(auction_items)")
        columns = [col[1] for col in cursor.fetchall()]

        if "sport" in columns:
            print("Column 'sport' already exists in auction_items table")
        else:
            # Add the column
            print("Adding 'sport' column to auction_items table...")
            cursor.execute("ALTER TABLE auction_items ADD COLUMN sport VARCHAR(20)")
            print("Column added successfully")

        # Check if index exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='ix_auction_items_sport'")
        index_exists = cursor.fetchone() is not None

        if index_exists:
            print("Index 'ix_auction_items_sport' already exists")
        else:
            # Create index
            print("Creating index on sport column...")
            cursor.execute("CREATE INDEX ix_auction_items_sport ON auction_items(sport)")
            print("Index created successfully")

        conn.commit()
        print("\nMigration completed successfully!")

        # Show current schema
        print("\nCurrent auction_items schema:")
        cursor.execute("PRAGMA table_info(auction_items)")
        for col in cursor.fetchall():
            print(f"  {col[1]}: {col[2]}")

    except Exception as e:
        print(f"ERROR: {e}")
        conn.rollback()
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    add_sport_column()
