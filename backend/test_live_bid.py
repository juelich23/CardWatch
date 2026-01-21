"""
Test live bid placement - see exact response
"""
import asyncio
import sys
sys.path.insert(0, '/Users/nickjuelich/Desktop/Code/BulkBidding/backend')

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.services.auction_auth.goldin_auth import GoldinAuthService

DATABASE_URL = "sqlite+aiosqlite:///auction_data.db"
engine = create_async_engine(DATABASE_URL, echo=False)
async_session_maker = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def test_live_bid():
    async with async_session_maker() as db:
        # Find a $10 item
        from sqlalchemy import select, text
        result = await db.execute(text("""
            SELECT id, item_url, title, current_bid FROM auction_items
            WHERE auction_house = 'goldin' AND status = 'Live' AND current_bid = 10
            LIMIT 1
        """))
        row = result.fetchone()

        if not row:
            print("No $10 item found!")
            return

        item_id, item_url, title, current_bid = row
        bid_amount = 16  # Bid higher to win

        print(f"Item: {title[:60]}...")
        print(f"URL: {item_url}")
        print(f"Current bid: ${current_bid}")
        print(f"Our bid: ${bid_amount}")
        print()

        goldin_auth = GoldinAuthService(db)

        print("Placing bid...")
        success, message = await goldin_auth.place_bid(
            user_id=2,  # Your user ID
            item_url=item_url,
            bid_amount=bid_amount
        )

        print(f"\n=== RESULT ===")
        print(f"Success: {success}")
        print(f"Message: {message}")

asyncio.run(test_live_bid())
