#!/usr/bin/env python3
"""
Backfill script to populate sport field for existing auction items.
Uses sqlite3 directly to avoid dependency on full backend stack.
"""
import sqlite3
import sys
from pathlib import Path
from collections import Counter

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.utils.sport_detection import detect_sport_from_item

# Database path
DB_PATH = Path(__file__).parent.parent / "auction_data.db"
BATCH_SIZE = 500


def backfill_sport():
    """Backfill sport field for all existing items"""
    print(f"Database path: {DB_PATH}")

    if not DB_PATH.exists():
        print(f"ERROR: Database not found at {DB_PATH}")
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        # Get total count of items without sport
        cursor.execute("SELECT COUNT(*) FROM auction_items WHERE sport IS NULL")
        total_without_sport = cursor.fetchone()[0]

        print(f"Found {total_without_sport} items without sport field")

        if total_without_sport == 0:
            print("All items already have sport field populated!")
            show_distribution(cursor)
            return

        # Process in batches
        processed = 0
        sport_counter = Counter()

        while True:
            # Get batch of items without sport
            cursor.execute("""
                SELECT id, title, description, category
                FROM auction_items
                WHERE sport IS NULL
                LIMIT ?
            """, (BATCH_SIZE,))

            items = cursor.fetchall()

            if not items:
                break

            # Update each item
            updates = []
            for item in items:
                sport = detect_sport_from_item(
                    title=item['title'],
                    description=item['description'],
                    category=item['category']
                )
                updates.append((sport.value, item['id']))
                sport_counter[sport.value] += 1

            # Batch update
            cursor.executemany(
                "UPDATE auction_items SET sport = ? WHERE id = ?",
                updates
            )
            conn.commit()

            processed += len(items)
            pct = processed * 100 // total_without_sport
            print(f"Processed {processed}/{total_without_sport} items ({pct}%)")

        print(f"\nBackfill complete! Processed {processed} items")
        print("\nSport distribution from backfill:")
        for sport, count in sport_counter.most_common():
            print(f"  {sport}: {count}")

        # Show overall distribution
        show_distribution(cursor)

    except Exception as e:
        print(f"ERROR: {e}")
        conn.rollback()
        sys.exit(1)
    finally:
        conn.close()


def show_distribution(cursor):
    """Show sport distribution across all items"""
    print("\n" + "=" * 50)
    print("Overall Sport Distribution:")
    print("=" * 50)

    cursor.execute("""
        SELECT sport, COUNT(*) as count
        FROM auction_items
        GROUP BY sport
        ORDER BY count DESC
    """)

    distribution = cursor.fetchall()
    total = sum(row['count'] for row in distribution)

    for row in distribution:
        sport_name = row['sport'] or "NULL"
        count = row['count']
        percentage = count * 100 / total if total > 0 else 0
        print(f"  {sport_name:15} {count:6} ({percentage:5.1f}%)")

    print(f"\n  {'TOTAL':15} {total:6}")


if __name__ == "__main__":
    backfill_sport()
