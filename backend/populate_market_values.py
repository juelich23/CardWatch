#!/usr/bin/env python3
"""
Pre-populate market value estimates for auction items.
Runs in batches to avoid overwhelming the API.
"""

import asyncio
import sys
sys.path.insert(0, '/Users/nickjuelich/Desktop/Code/BulkBidding/backend')

from datetime import datetime
from sqlalchemy import select, and_
from app.database import init_db, get_db
from app.models import AuctionItem
from app.services.market_value import MarketValueEstimator


async def populate_market_values(batch_size: int = 50, max_items: int = 500):
    """Populate market values for items that don't have them yet."""

    print(f"Initializing database...")
    await init_db()

    estimator = MarketValueEstimator()

    async for db in get_db():
        # Get items without market value estimates
        # Prioritize items with higher bids (more valuable to estimate)
        query = select(AuctionItem).where(
            and_(
                AuctionItem.status == "Live",
                AuctionItem.end_time > datetime.utcnow(),
                AuctionItem.market_value_avg.is_(None),
                AuctionItem.current_bid > 0
            )
        ).order_by(AuctionItem.current_bid.desc()).limit(max_items)

        result = await db.execute(query)
        items = result.scalars().all()

        print(f"Found {len(items)} items without market value estimates")

        if not items:
            print("No items to process!")
            return

        # Extract item data to plain dicts to avoid lazy loading issues
        item_data = []
        for item in items:
            item_data.append({
                'id': item.id,
                'title': item.title,
                'grading_company': item.grading_company,
                'grade': item.grade,
                'current_bid': item.current_bid,
            })

        processed = 0
        errors = 0

        for i, data in enumerate(item_data):
            try:
                print(f"[{i+1}/{len(item_data)}] Estimating: {data['title'][:60]}...")

                estimate = estimator.estimate_value(
                    title=data['title'],
                    grading_company=data['grading_company'],
                    grade=data['grade'],
                    current_bid=data['current_bid'],
                )

                if estimate.get("estimated_average"):
                    # Update item directly by ID
                    await db.execute(
                        AuctionItem.__table__.update()
                        .where(AuctionItem.id == data['id'])
                        .values(
                            market_value_low=estimate.get("estimated_low"),
                            market_value_high=estimate.get("estimated_high"),
                            market_value_avg=estimate.get("estimated_average"),
                            market_value_confidence=estimate.get("confidence", "low"),
                            market_value_notes=estimate.get("notes", ""),
                            market_value_updated_at=datetime.utcnow()
                        )
                    )
                    processed += 1

                    # Calculate value percentage
                    avg = estimate.get("estimated_average")
                    if data['current_bid'] and avg:
                        pct = (data['current_bid'] / avg) * 100
                        print(f"   -> Est: ${avg:,.0f} ({pct:.0f}% of value)")
                else:
                    print(f"   -> No estimate returned")
                    errors += 1

                # Commit every batch_size items
                if (i + 1) % batch_size == 0:
                    try:
                        await db.commit()
                        print(f"   Committed batch ({processed} processed, {errors} errors)")
                    except Exception as commit_err:
                        print(f"   Commit failed: {commit_err}")
                        await db.rollback()

                # Small delay to avoid rate limiting
                await asyncio.sleep(0.1)

            except Exception as e:
                print(f"   -> Error: {e}")
                errors += 1
                continue

        # Final commit
        try:
            await db.commit()
        except Exception as e:
            print(f"Final commit failed: {e}")
            await db.rollback()

        print(f"\n{'='*50}")
        print(f"Done! Processed {processed} items, {errors} errors")
        print(f"{'='*50}")

        break


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--max", type=int, default=500, help="Max items to process")
    parser.add_argument("--batch", type=int, default=50, help="Batch size for commits")
    args = parser.parse_args()

    asyncio.run(populate_market_values(batch_size=args.batch, max_items=args.max))
