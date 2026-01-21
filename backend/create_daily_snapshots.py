#!/usr/bin/env python3
"""
Create daily price snapshots for all active auction items.
Run this script daily via cron job:
    0 0 * * * cd /path/to/backend && python create_daily_snapshots.py
"""
import asyncio
import sys
from datetime import datetime

# Add the app directory to the path
sys.path.insert(0, '.')

from app.database import init_db, get_db
from app.services.price_snapshot_service import PriceSnapshotService


async def main():
    print(f"=== Daily Price Snapshot Job ===")
    print(f"Started at: {datetime.utcnow().isoformat()}")
    print()

    # Initialize database
    await init_db()

    # Get database session
    async for db in get_db():
        service = PriceSnapshotService(db)

        # Create snapshots
        count = await service.create_daily_snapshots()
        print(f"\nCreated {count} price snapshots")

        # Optional: Clean up old snapshots (keep 90 days)
        # deleted = await service.cleanup_old_snapshots(days_to_keep=90)
        # print(f"Cleaned up {deleted} old snapshots")

        break

    print(f"\nCompleted at: {datetime.utcnow().isoformat()}")


if __name__ == "__main__":
    asyncio.run(main())
