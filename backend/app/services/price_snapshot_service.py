"""
Price Snapshot Service for historical price tracking
"""
from datetime import datetime, timedelta
from typing import List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuctionItem, PriceSnapshot


class PriceSnapshotService:
    """Service for creating and querying price snapshots"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_daily_snapshots(self, batch_size: int = 500) -> int:
        """
        Create snapshots for all active items.
        Only creates one snapshot per item per day.

        Args:
            batch_size: Number of items to process in each batch

        Returns:
            Number of snapshots created
        """
        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        created_count = 0

        # Get all active items
        query = select(AuctionItem).where(AuctionItem.status == "Live")
        result = await self.db.execute(query)
        items = result.scalars().all()

        print(f"Found {len(items)} active items to snapshot")

        for item in items:
            # Check if snapshot already exists for today
            existing_query = select(PriceSnapshot).where(
                PriceSnapshot.item_id == item.id,
                PriceSnapshot.snapshot_date == today
            )
            result = await self.db.execute(existing_query)
            existing = result.scalar_one_or_none()

            if existing:
                continue

            # Create new snapshot
            snapshot = PriceSnapshot(
                item_id=item.id,
                current_bid=item.current_bid,
                bid_count=item.bid_count or 0,
                status=item.status,
                snapshot_date=today
            )
            self.db.add(snapshot)
            created_count += 1

            # Commit in batches to avoid memory issues
            if created_count % batch_size == 0:
                await self.db.commit()
                print(f"Created {created_count} snapshots...")

        # Final commit
        await self.db.commit()
        print(f"Created {created_count} total snapshots")

        return created_count

    async def get_price_history(
        self,
        item_id: int,
        days: int = 30
    ) -> List[PriceSnapshot]:
        """
        Get price history for an item.

        Args:
            item_id: ID of the auction item
            days: Number of days of history to fetch

        Returns:
            List of price snapshots ordered by date ascending
        """
        cutoff = datetime.utcnow() - timedelta(days=days)

        query = (
            select(PriceSnapshot)
            .where(
                PriceSnapshot.item_id == item_id,
                PriceSnapshot.snapshot_date >= cutoff
            )
            .order_by(PriceSnapshot.snapshot_date.asc())
        )

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_latest_snapshot(self, item_id: int) -> PriceSnapshot | None:
        """Get the most recent snapshot for an item"""
        query = (
            select(PriceSnapshot)
            .where(PriceSnapshot.item_id == item_id)
            .order_by(PriceSnapshot.snapshot_date.desc())
            .limit(1)
        )

        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def cleanup_old_snapshots(self, days_to_keep: int = 90) -> int:
        """
        Remove snapshots older than specified days.

        Args:
            days_to_keep: Number of days of history to keep

        Returns:
            Number of snapshots deleted
        """
        cutoff = datetime.utcnow() - timedelta(days=days_to_keep)

        # Get count of snapshots to delete
        count_query = select(PriceSnapshot).where(
            PriceSnapshot.snapshot_date < cutoff
        )
        result = await self.db.execute(count_query)
        snapshots_to_delete = result.scalars().all()
        count = len(snapshots_to_delete)

        # Delete old snapshots
        for snapshot in snapshots_to_delete:
            await self.db.delete(snapshot)

        await self.db.commit()
        return count
