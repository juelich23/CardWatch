#!/usr/bin/env python3
"""
Migration script to classify existing auction items with item_type.

Usage:
    python -m scripts.migrate_item_types

This script:
1. Queries all auction items without an item_type
2. Runs detection algorithm on each item
3. Updates items in batches of 1000
4. Reports progress and statistics
"""
import asyncio
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from collections import Counter
from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_maker
from app.models import AuctionItem
from app.utils.item_type_detection import detect_item_type, ItemType


BATCH_SIZE = 1000


async def count_items_by_type(session: AsyncSession) -> dict:
    """Count items by their current item_type."""
    query = (
        select(AuctionItem.item_type, func.count(AuctionItem.id))
        .group_by(AuctionItem.item_type)
    )
    result = await session.execute(query)
    return {row[0] or "NULL": row[1] for row in result.fetchall()}


async def migrate_item_types():
    """Migrate existing items to have item_type classifications."""
    print("=" * 60)
    print("Item Type Migration Script")
    print("=" * 60)

    async with async_session_maker() as session:
        # Get current state
        print("\nCurrent item_type distribution:")
        counts_before = await count_items_by_type(session)
        for item_type, count in sorted(counts_before.items()):
            print(f"  {item_type}: {count:,}")

        # Count items needing migration
        query = select(func.count(AuctionItem.id)).where(AuctionItem.item_type.is_(None))
        result = await session.execute(query)
        total_to_migrate = result.scalar() or 0

        if total_to_migrate == 0:
            print("\nNo items need migration. All items already have item_type set.")
            return

        print(f"\nItems to migrate: {total_to_migrate:,}")
        print(f"Batch size: {BATCH_SIZE}")
        print("\nStarting migration...")

        # Process in batches
        migrated = 0
        type_counts = Counter()

        while migrated < total_to_migrate:
            # Fetch batch of items without item_type
            query = (
                select(AuctionItem)
                .where(AuctionItem.item_type.is_(None))
                .limit(BATCH_SIZE)
            )
            result = await session.execute(query)
            items = list(result.scalars().all())

            if not items:
                break

            # Classify and update each item
            for item in items:
                item_type = detect_item_type(
                    title=item.title,
                    description=item.description,
                    category=item.category,
                    grading_company=item.grading_company,
                )
                item.item_type = item_type.value
                type_counts[item_type.value] += 1

            # Commit batch
            await session.commit()
            migrated += len(items)

            # Progress update
            progress = (migrated / total_to_migrate) * 100
            print(f"  Migrated {migrated:,}/{total_to_migrate:,} ({progress:.1f}%)", flush=True)

        print("\nMigration complete!")
        print("\nClassification results:")
        for item_type, count in sorted(type_counts.items()):
            print(f"  {item_type}: {count:,}")

        # Final state
        print("\nFinal item_type distribution:")
        counts_after = await count_items_by_type(session)
        for item_type, count in sorted(counts_after.items()):
            print(f"  {item_type}: {count:,}")


if __name__ == "__main__":
    asyncio.run(migrate_item_types())
